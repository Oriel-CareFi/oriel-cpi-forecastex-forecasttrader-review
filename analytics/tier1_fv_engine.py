from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from analytics.brier_calibration import (
    CalibrationSummary,
    compute_calibration_summary,
    load_calibration_history,
)

ANNUALIZATION_DAYS = 365.0
DEFAULT_BASE_INDEX = 100.0
ONE_MONTH_DAYS = 30
THREE_MONTH_DAYS = 90
SIX_MONTH_DAYS = 180

CURVE_VALUE_COLUMNS = ["expected_yoy_pct", "index_level", "std_dev_pct"]

# ---------------------------------------------------------------------------
# Hardening V1 config
# ---------------------------------------------------------------------------
MAX_MEDIAN_AGE_MINUTES = 5
STALE_QUOTE_SECONDS = 300
FRESH_QUOTE_SECONDS = 60
MIN_ELIGIBLE_CONSTITUENTS = 3
MIN_COVERAGE_SCORE = 45.0
MIN_CONSISTENCY_SCORE = 50.0
MIN_PUBLISHABILITY_SCORE = 55.0
MIN_HISTORICAL_CALIBRATION_SCORE = 40.0
BLEND_ALPHA = 0.35
TARGET_THRESHOLDS = [2.0, 2.5, 3.0]
Z_90 = 1.645  # z-score for 90% confidence interval


@dataclass
class BlendMetadata:
    requested_kalshi_weight: float
    requested_forecastex_weight: float
    effective_kalshi_weight: float
    effective_forecastex_weight: float
    kalshi_eligible: bool
    forecastex_eligible: bool
    weighting_method: str
    eligibility_rule: str


@dataclass
class Tier1Snapshot:
    official_index_print: float
    spot_index: float
    fv_index: float
    perp_price: float
    basis_bp: float
    annualized_carry_bp: float
    front_expected_yoy_pct: float
    implied_1m_yoy_pct: float
    implied_3m_yoy_pct: float
    implied_6m_yoy_pct: float
    term_structure_pct: float
    publishability_label: str
    confidence_label: str
    confidence_score_pct: float
    requested_kalshi_weight_pct: float
    requested_forecastex_weight_pct: float
    effective_kalshi_weight_pct: float
    effective_forecastex_weight_pct: float
    kalshi_eligible: bool
    forecastex_eligible: bool
    weighting_method: str
    eligibility_rule: str
    fv_horizon_days: int


def interpolate_curve_value(curve: pd.DataFrame, horizon_days: int, value_col: str) -> float:
    if horizon_days < 0:
        raise ValueError("horizon_days must be non-negative")

    x = curve["days_from_valuation"].to_numpy(dtype=float)
    y = curve[value_col].to_numpy(dtype=float)

    if horizon_days <= x.min():
        return float(y[0])
    if horizon_days >= x.max():
        return float(y[-1])

    return float(np.interp(horizon_days, x, y))


def _aggregate_curve_from_constituents(constituents: pd.DataFrame, venue_name: str) -> pd.DataFrame:
    work = constituents.copy()
    if "included_in_curve" in work.columns:
        eligible = work[work["included_in_curve"].astype(bool)].copy()
    else:
        eligible = work[work["eligible"]].copy()
    if eligible.empty:
        eligible = work[work["eligible"]].copy() if "eligible" in work.columns else work.copy()
    if eligible.empty:
        eligible = work.copy()

    rows = []
    for (target_month, days_from_valuation), grp in eligible.groupby(["target_month", "days_from_valuation"], sort=True):
        w = grp["weight"].astype(float)
        if w.sum() <= 0:
            w = pd.Series(np.ones(len(grp)), index=grp.index, dtype=float)
        w = w / w.sum()
        rows.append(
            {
                "target_month": target_month,
                "days_from_valuation": int(days_from_valuation),
                "expected_yoy_pct": float(np.average(grp["expected_yoy_pct"], weights=w)),
                "index_level": float(np.average(grp["index_level"], weights=w)),
                "std_dev_pct": float(np.average(grp["std_dev_pct"], weights=w)),
                "source": venue_name,
                "n_constituents": int(len(grp)),
                "eligible_constituents": int(grp["eligible"].sum()),
                "total_weight": float(grp["weight"].sum()),
            }
        )

    return pd.DataFrame(rows).sort_values("days_from_valuation").reset_index(drop=True)


def build_kalshi_curve_from_constituents(constituents: pd.DataFrame) -> pd.DataFrame:
    return _aggregate_curve_from_constituents(constituents, "Kalshi")


def build_forecastex_curve_from_constituents(constituents: pd.DataFrame) -> pd.DataFrame:
    return _aggregate_curve_from_constituents(constituents, "ForecastEx")


def compute_effective_blend(
    kalshi_weight: float,
    forecastex_weight: float,
    kalshi_eligible: bool,
    forecastex_eligible: bool,
) -> BlendMetadata:
    requested_k = max(0.0, float(kalshi_weight))
    requested_f = max(0.0, float(forecastex_weight))

    if kalshi_eligible and forecastex_eligible:
        total = requested_k + requested_f
        if total <= 0:
            eff_k = eff_f = 0.5
        else:
            eff_k = requested_k / total
            eff_f = requested_f / total
    elif kalshi_eligible:
        eff_k, eff_f = 1.0, 0.0
    elif forecastex_eligible:
        eff_k, eff_f = 0.0, 1.0
    else:
        eff_k = eff_f = 0.5

    return BlendMetadata(
        requested_kalshi_weight=requested_k,
        requested_forecastex_weight=requested_f,
        effective_kalshi_weight=eff_k,
        effective_forecastex_weight=eff_f,
        kalshi_eligible=kalshi_eligible,
        forecastex_eligible=forecastex_eligible,
        weighting_method="Eligible-source normalized weighted average",
        eligibility_rule="If one venue is ineligible, weight shifts to eligible venue; if both are ineligible, blend is flagged for review.",
    )


def blend_curves(
    kalshi_curve: pd.DataFrame,
    forecastex_curve: pd.DataFrame,
    kalshi_weight: float,
    forecastex_weight: float,
    kalshi_eligible: bool,
    forecastex_eligible: bool,
) -> tuple[pd.DataFrame, BlendMetadata]:
    meta = compute_effective_blend(kalshi_weight, forecastex_weight, kalshi_eligible, forecastex_eligible)

    merged = kalshi_curve.merge(
        forecastex_curve,
        on=["target_month", "days_from_valuation"],
        how="outer",
        suffixes=("_kalshi", "_forecastex"),
    ).sort_values("days_from_valuation").reset_index(drop=True)

    for col in CURVE_VALUE_COLUMNS:
        kcol = f"{col}_kalshi"
        fcol = f"{col}_forecastex"
        merged[kcol] = merged[kcol].astype(float)
        merged[fcol] = merged[fcol].astype(float)
        merged[col] = (
            meta.effective_kalshi_weight * merged[kcol].fillna(merged[fcol])
            + meta.effective_forecastex_weight * merged[fcol].fillna(merged[kcol])
        )

    merged["source"] = "Oriel Blend"
    merged["kalshi_weight"] = meta.effective_kalshi_weight
    merged["forecastex_weight"] = meta.effective_forecastex_weight
    merged["publishable"] = bool(kalshi_eligible or forecastex_eligible)

    return merged[["target_month", "days_from_valuation", "expected_yoy_pct", "index_level", "std_dev_pct", "source", "kalshi_weight", "forecastex_weight", "publishable"]], meta


def compute_spot_index(curve: pd.DataFrame) -> float:
    return float(curve.iloc[0]["index_level"])


def compute_front_expected_yoy(curve: pd.DataFrame) -> float:
    return float(curve.iloc[0]["expected_yoy_pct"])


def compute_implied_yoy(curve: pd.DataFrame, horizon_days: int) -> float:
    return interpolate_curve_value(curve, horizon_days, "expected_yoy_pct")


def compute_fair_value(curve: pd.DataFrame, horizon_days: int) -> float:
    return interpolate_curve_value(curve, horizon_days, "index_level")


def compute_basis_bp(perp_price: float, fair_value: float) -> float:
    if fair_value == 0:
        return 0.0
    return float((perp_price / fair_value - 1.0) * 10000.0)


def compute_annualized_carry_bp(spot_index: float, fair_value: float, horizon_days: int) -> float:
    if horizon_days <= 0 or spot_index == 0:
        return 0.0
    simple_return = fair_value / spot_index - 1.0
    annualized_return = simple_return * (ANNUALIZATION_DAYS / horizon_days)
    return float(annualized_return * 10000.0)


def perp_price_from_basis(fair_value: float, basis_bp: float) -> float:
    return float(fair_value * (1.0 + basis_bp / 10000.0))


def compute_term_structure_pct(curve: pd.DataFrame) -> float:
    return float(compute_implied_yoy(curve, SIX_MONTH_DAYS) - compute_implied_yoy(curve, ONE_MONTH_DAYS))


def compute_publishability(curve: pd.DataFrame, blend_metadata: BlendMetadata) -> tuple[str, str, float]:
    maturity_score = min(1.0, float(curve["days_from_valuation"].max()) / float(SIX_MONTH_DAYS))
    source_score = 1.0 if (blend_metadata.kalshi_eligible and blend_metadata.forecastex_eligible) else 0.7 if (blend_metadata.kalshi_eligible or blend_metadata.forecastex_eligible) else 0.0
    balance_score = 1.0 - abs(blend_metadata.effective_kalshi_weight - blend_metadata.effective_forecastex_weight)
    confidence_score = max(0.0, min(1.0, 0.45 * maturity_score + 0.35 * source_score + 0.20 * balance_score))

    if confidence_score >= 0.85:
        publishability = "Eligible"
        confidence = "High"
    elif confidence_score >= 0.65:
        publishability = "Review"
        confidence = "Moderate"
    else:
        publishability = "Draft"
        confidence = "Low"

    return publishability, confidence, float(confidence_score * 100.0)


def build_tier1_snapshot(
    curve: pd.DataFrame,
    fv_horizon_days: int,
    perp_basis_bp: float,
    blend_metadata: BlendMetadata | None = None,
) -> Tier1Snapshot:
    if blend_metadata is None:
        blend_metadata = compute_effective_blend(0.5, 0.5, True, True)
    spot_index = compute_spot_index(curve)
    fv_index = compute_fair_value(curve, fv_horizon_days)
    perp_price = perp_price_from_basis(fv_index, perp_basis_bp)
    annualized_carry_bp = compute_annualized_carry_bp(spot_index, fv_index, fv_horizon_days)
    front_expected_yoy_pct = compute_front_expected_yoy(curve)
    implied_1m_yoy_pct = compute_implied_yoy(curve, ONE_MONTH_DAYS)
    implied_3m_yoy_pct = compute_implied_yoy(curve, THREE_MONTH_DAYS)
    implied_6m_yoy_pct = compute_implied_yoy(curve, SIX_MONTH_DAYS)
    term_structure_pct = compute_term_structure_pct(curve)
    publishability_label, confidence_label, confidence_score_pct = compute_publishability(curve, blend_metadata)

    return Tier1Snapshot(
        official_index_print=DEFAULT_BASE_INDEX,
        spot_index=spot_index,
        fv_index=fv_index,
        perp_price=perp_price,
        basis_bp=compute_basis_bp(perp_price, fv_index),
        annualized_carry_bp=annualized_carry_bp,
        front_expected_yoy_pct=front_expected_yoy_pct,
        implied_1m_yoy_pct=implied_1m_yoy_pct,
        implied_3m_yoy_pct=implied_3m_yoy_pct,
        implied_6m_yoy_pct=implied_6m_yoy_pct,
        term_structure_pct=term_structure_pct,
        publishability_label=publishability_label,
        confidence_label=confidence_label,
        confidence_score_pct=confidence_score_pct,
        requested_kalshi_weight_pct=blend_metadata.requested_kalshi_weight * 100.0,
        requested_forecastex_weight_pct=blend_metadata.requested_forecastex_weight * 100.0,
        effective_kalshi_weight_pct=blend_metadata.effective_kalshi_weight * 100.0,
        effective_forecastex_weight_pct=blend_metadata.effective_forecastex_weight * 100.0,
        kalshi_eligible=blend_metadata.kalshi_eligible,
        forecastex_eligible=blend_metadata.forecastex_eligible,
        weighting_method=blend_metadata.weighting_method,
        eligibility_rule=blend_metadata.eligibility_rule,
        fv_horizon_days=fv_horizon_days,
    )


def build_display_table(curve: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    df = curve.copy()
    df["target_month"] = df["target_month"].dt.strftime("%Y-%m-%d")
    df["fv_marker"] = np.where(df["days_from_valuation"] == horizon_days, "FV Horizon", "")
    return df



def load_tier1_curve(path) -> pd.DataFrame:
    required = ["target_month", "days_from_valuation", "expected_yoy_pct", "index_level", "std_dev_pct"]
    df = pd.read_csv(path)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    df = df.copy()
    df["target_month"] = pd.to_datetime(df["target_month"])
    return df.sort_values("days_from_valuation").reset_index(drop=True)


def load_tier1_constituents(path) -> pd.DataFrame:
    required = ["target_month", "days_from_valuation", "expected_yoy_pct", "index_level", "std_dev_pct", "weight", "eligible"]
    df = pd.read_csv(path)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    df = df.copy()
    df["target_month"] = pd.to_datetime(df["target_month"])
    df["eligible"] = df["eligible"].astype(bool)
    return df.sort_values(["days_from_valuation", "target_month"]).reset_index(drop=True)


# ============================================================================
# HARDENING PACKAGE V1  --  CPI Forward-Reference Engine Extensions
# ============================================================================
# Everything below is additive.  No existing function or dataclass is modified.
# ============================================================================

import math
from datetime import datetime, timezone

try:
    from scipy.stats import norm as _scipy_norm

    def _normal_sf(z: float) -> float:
        return float(_scipy_norm.sf(z))
except ImportError:  # pragma: no cover – scipy optional for demo
    def _normal_sf(z: float) -> float:
        """Abramowitz & Stegun rational approximation of 1-Phi(z)."""
        if z < 0:
            return 1.0 - _normal_sf(-z)
        t = 1.0 / (1.0 + 0.2316419 * z)
        d = 0.3989422804014327  # 1/sqrt(2*pi)
        poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
        return max(0.0, min(1.0, d * math.exp(-0.5 * z * z) * poly))


# ---------------------------------------------------------------------------
# 1.  New dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VenueCurvePoint:
    horizon_months: float
    mean_pct: float
    std_dev_pct: float | None = None
    band_1sigma_low_pct: float | None = None
    band_1sigma_high_pct: float | None = None
    band_90_low_pct: float | None = None
    band_90_high_pct: float | None = None
    threshold_probs: dict | None = None
    constituent_count: int = 0
    eligible_constituent_count: int = 0
    constituent_dispersion_bp: float | None = None


@dataclass
class BlendedReferencePoint:
    horizon_months: float
    blended_mean_pct: float
    blended_std_dev_pct: float | None = None
    blended_band_1sigma_low_pct: float | None = None
    blended_band_1sigma_high_pct: float | None = None
    blended_band_90_low_pct: float | None = None
    blended_band_90_high_pct: float | None = None
    blended_threshold_probs: dict | None = None
    source_residual_bp: dict | None = None
    distribution_confidence_score: float = 0.0


@dataclass
class VenueWeightDiagnostics:
    venue: str
    requested_weight: float
    raw_venue_score: float
    raw_score_weight: float
    effective_weight: float
    eligible: bool
    eligibility_reason: str | None = None
    liquidity_score: float = 0.0
    spread_quality_score: float = 0.0
    freshness_score: float = 0.0
    coverage_score: float = 0.0
    internal_consistency_score: float = 0.0
    historical_calibration_score: float = 50.0
    brier_skill_score: float = 50.0
    log_loss_skill_score: float = 50.0
    calibration_bias_score: float = 50.0
    calibration_sample_size_score: float = 0.0
    calibration_sample_size: int = 0
    weighted_mean_brier_score: float = 0.25
    weighted_mean_log_loss: float = 0.6931
    weighted_mean_abs_error_pct: float = 0.0
    weighted_bias_pct: float = 0.0
    weighted_hit_rate: float = 0.5
    calibration_methodology_note: str | None = None
    contract_family_calibration: dict | None = None
    horizon_bucket_calibration: dict | None = None
    median_quote_age_seconds: float | None = None
    snapshot_span_seconds: float | None = None


@dataclass
class VenueFreshnessSummary:
    venue: str
    median_quote_age_seconds: float = 0.0
    max_quote_age_seconds: float = 0.0
    min_quote_age_seconds: float = 0.0
    stale_quote_fraction: float = 0.0
    fresh_quote_fraction: float = 0.0
    snapshot_span_seconds: float = 0.0


@dataclass
class BlendedFreshnessSummary:
    blended_snapshot_start_utc: str = ""
    blended_snapshot_end_utc: str = ""
    blended_snapshot_span_seconds: float = 0.0
    kalshi_snapshot_median_age_seconds: float = 0.0
    forecastex_snapshot_median_age_seconds: float = 0.0
    cross_venue_median_age_gap_seconds: float = 0.0
    freshness_commentary: str = ""


# ---------------------------------------------------------------------------
# 2.  Distribution metric functions
# ---------------------------------------------------------------------------

def _threshold_probs(mean: float, std: float, thresholds: list[float] | None = None) -> dict:
    """Compute P(CPI > threshold) for each target threshold using normal CDF."""
    thresholds = thresholds or TARGET_THRESHOLDS
    probs: dict[str, float] = {}
    for t in thresholds:
        if std > 0:
            z = (t - mean) / std
            probs[f"gt_{str(t).replace('.', '_')}"] = round(_normal_sf(z), 4)
        else:
            probs[f"gt_{str(t).replace('.', '_')}"] = 1.0 if mean > t else 0.0
    return probs


def compute_distribution_metrics(
    curve: pd.DataFrame,
    constituents: pd.DataFrame | None = None,
) -> list[VenueCurvePoint]:
    """Build distribution-aware curve points from a venue curve DataFrame."""
    points: list[VenueCurvePoint] = []
    for _, row in curve.iterrows():
        mean = float(row["expected_yoy_pct"])
        std = float(row.get("std_dev_pct", 0.0) or 0.0)
        days = float(row["days_from_valuation"])
        horizon_months = round(days / 30.0, 2)

        band_1_lo = mean - std if std > 0 else None
        band_1_hi = mean + std if std > 0 else None
        band_90_lo = mean - Z_90 * std if std > 0 else None
        band_90_hi = mean + Z_90 * std if std > 0 else None

        probs = _threshold_probs(mean, std) if std > 0 else None

        n_const = int(row.get("n_constituents", 0) or 0)
        n_eligible = int(row.get("eligible_constituents", 0) or 0)

        dispersion_bp: float | None = None
        if constituents is not None and not constituents.empty:
            mat_group = constituents[constituents["days_from_valuation"] == int(row["days_from_valuation"])]
            if len(mat_group) >= 2:
                vals = mat_group["expected_yoy_pct"].astype(float)
                dispersion_bp = round((vals.max() - vals.min()) * 100.0, 2)

        points.append(
            VenueCurvePoint(
                horizon_months=horizon_months,
                mean_pct=round(mean, 4),
                std_dev_pct=round(std, 4) if std > 0 else None,
                band_1sigma_low_pct=round(band_1_lo, 4) if band_1_lo is not None else None,
                band_1sigma_high_pct=round(band_1_hi, 4) if band_1_hi is not None else None,
                band_90_low_pct=round(band_90_lo, 4) if band_90_lo is not None else None,
                band_90_high_pct=round(band_90_hi, 4) if band_90_hi is not None else None,
                threshold_probs=probs,
                constituent_count=n_const,
                eligible_constituent_count=n_eligible,
                constituent_dispersion_bp=dispersion_bp,
            )
        )
    return points


def compute_blended_reference_points(
    blended_curve: pd.DataFrame,
    kalshi_curve: pd.DataFrame | None = None,
    forecastex_curve: pd.DataFrame | None = None,
) -> list[BlendedReferencePoint]:
    """Build distribution-aware blended reference points with source residuals."""
    points: list[BlendedReferencePoint] = []
    for _, row in blended_curve.iterrows():
        mean = float(row["expected_yoy_pct"])
        std = float(row.get("std_dev_pct", 0.0) or 0.0)
        days = int(row["days_from_valuation"])
        horizon_months = round(days / 30.0, 2)

        band_1_lo = mean - std if std > 0 else None
        band_1_hi = mean + std if std > 0 else None
        band_90_lo = mean - Z_90 * std if std > 0 else None
        band_90_hi = mean + Z_90 * std if std > 0 else None
        probs = _threshold_probs(mean, std) if std > 0 else None

        residuals: dict[str, float] = {}
        for label, src_curve in [("kalshi", kalshi_curve), ("forecastex", forecastex_curve)]:
            if src_curve is not None and not src_curve.empty:
                matched = src_curve[src_curve["days_from_valuation"] == days]
                if not matched.empty:
                    src_mean = float(matched.iloc[0]["expected_yoy_pct"])
                    residuals[label] = round((src_mean - mean) * 100.0, 2)  # basis points
        if not residuals:
            residuals = None

        confidence = compute_distribution_confidence_score_from_values(
            threshold_probs=probs,
            std_dev=std,
            mean=mean,
        )

        points.append(
            BlendedReferencePoint(
                horizon_months=horizon_months,
                blended_mean_pct=round(mean, 4),
                blended_std_dev_pct=round(std, 4) if std > 0 else None,
                blended_band_1sigma_low_pct=round(band_1_lo, 4) if band_1_lo is not None else None,
                blended_band_1sigma_high_pct=round(band_1_hi, 4) if band_1_hi is not None else None,
                blended_band_90_low_pct=round(band_90_lo, 4) if band_90_lo is not None else None,
                blended_band_90_high_pct=round(band_90_hi, 4) if band_90_hi is not None else None,
                blended_threshold_probs=probs,
                source_residual_bp=residuals,
                distribution_confidence_score=confidence,
            )
        )
    return points


def compute_distribution_confidence_score_from_values(
    threshold_probs: dict | None = None,
    std_dev: float = 0.0,
    mean: float = 0.0,
    freshness_score: float = 80.0,
    liquidity_score: float = 75.0,
    is_interpolated: bool = False,
) -> float:
    """Compute 0-100 confidence score for a distribution point.

    Weights:
        0.30 * threshold_coverage
        0.25 * distribution_consistency
        0.20 * freshness
        0.15 * liquidity
        0.10 * interpolation_penalty
    """
    # Threshold coverage: how many thresholds have meaningful probabilities
    if threshold_probs:
        n_covered = sum(1 for v in threshold_probs.values() if 0.01 < v < 0.99)
        threshold_coverage = min(100.0, (n_covered / max(1, len(threshold_probs))) * 100.0)
    else:
        threshold_coverage = 0.0

    # Distribution consistency: narrower relative std -> higher score
    if std_dev > 0 and mean != 0:
        cv = abs(std_dev / mean)
        distribution_consistency = max(0.0, min(100.0, (1.0 - min(cv, 1.0)) * 100.0))
    else:
        distribution_consistency = 50.0

    interpolation_penalty = 0.0 if not is_interpolated else 50.0
    interp_score = 100.0 - interpolation_penalty

    score = (
        0.30 * threshold_coverage
        + 0.25 * distribution_consistency
        + 0.20 * freshness_score
        + 0.15 * liquidity_score
        + 0.10 * interp_score
    )
    return round(max(0.0, min(100.0, score)), 2)


def compute_distribution_confidence_score(point: VenueCurvePoint | BlendedReferencePoint) -> float:
    """Compute 0-100 confidence score for a dataclass distribution point."""
    if isinstance(point, VenueCurvePoint):
        return compute_distribution_confidence_score_from_values(
            threshold_probs=point.threshold_probs,
            std_dev=point.std_dev_pct or 0.0,
            mean=point.mean_pct,
        )
    return compute_distribution_confidence_score_from_values(
        threshold_probs=point.blended_threshold_probs,
        std_dev=point.blended_std_dev_pct or 0.0,
        mean=point.blended_mean_pct,
    )


# ---------------------------------------------------------------------------
# 3.  Venue scoring functions (for weighting engine)
# ---------------------------------------------------------------------------

def score_venue_liquidity(constituents: pd.DataFrame) -> float:
    """0-100 score based on OI, volume, depth.

    Heuristic for demo: uses eligible constituent count and weight dispersion
    as proxies for market depth.
    """
    if constituents.empty:
        return 0.0
    eligible = constituents[constituents["eligible"]] if "eligible" in constituents.columns else constituents
    n = len(eligible)
    if n == 0:
        return 10.0

    # More eligible constituents -> more liquid
    count_score = min(100.0, (n / 10.0) * 100.0)

    # Tighter weight dispersion -> deeper book
    weights = eligible["weight"].astype(float)
    if weights.sum() > 0 and len(weights) > 1:
        weight_cv = float(weights.std() / weights.mean()) if weights.mean() > 0 else 1.0
        dispersion_score = max(0.0, (1.0 - min(weight_cv, 1.0)) * 100.0)
    else:
        dispersion_score = 50.0

    return round(0.60 * count_score + 0.40 * dispersion_score, 2)


def score_venue_spread_quality(constituents: pd.DataFrame) -> float:
    """0-100 score based on spread tightness.

    Heuristic for demo: uses std_dev_pct of the constituent quotes within
    each maturity bucket as a proxy for quoted spread width.
    """
    if constituents.empty:
        return 0.0
    eligible = constituents[constituents["eligible"]] if "eligible" in constituents.columns else constituents
    if eligible.empty:
        return 10.0

    bucket_spreads: list[float] = []
    for _, grp in eligible.groupby("days_from_valuation"):
        if len(grp) >= 2:
            vals = grp["expected_yoy_pct"].astype(float)
            spread_bp = (vals.max() - vals.min()) * 100.0
            bucket_spreads.append(spread_bp)

    if not bucket_spreads:
        return 70.0  # single-quote buckets, assume decent

    avg_spread = float(np.mean(bucket_spreads))
    # Tighter spread -> higher score.  <5bp is excellent, >50bp is poor.
    if avg_spread <= 5.0:
        return 95.0
    if avg_spread >= 50.0:
        return 20.0
    return round(95.0 - (avg_spread - 5.0) * (75.0 / 45.0), 2)


def score_venue_freshness(constituents: pd.DataFrame) -> float:
    """0-100 score based on quote age.

    Since demo constituent CSVs don't have real timestamps, simulate ages:
    - If venue looks like Kalshi (tighter spreads, higher weight sums) -> fresher
    - Otherwise use slightly staler profile
    """
    if constituents.empty:
        return 0.0
    n = len(constituents)
    total_weight = float(constituents["weight"].sum())

    # Heuristic to guess venue character from data
    avg_weight = total_weight / max(n, 1)
    is_institutional = avg_weight > 0.15  # Kalshi-like

    if is_institutional:
        # Kalshi: fast refresh, median age ~25s
        simulated_median_age = 25.0
    else:
        # ForecastEx: slower, median age ~90s
        simulated_median_age = 90.0

    # Score: 0s -> 100, FRESH_QUOTE_SECONDS -> 80, STALE_QUOTE_SECONDS -> 0
    if simulated_median_age <= FRESH_QUOTE_SECONDS:
        return round(80.0 + 20.0 * (1.0 - simulated_median_age / FRESH_QUOTE_SECONDS), 2)
    if simulated_median_age >= STALE_QUOTE_SECONDS:
        return 0.0
    frac = (simulated_median_age - FRESH_QUOTE_SECONDS) / (STALE_QUOTE_SECONDS - FRESH_QUOTE_SECONDS)
    return round(80.0 * (1.0 - frac), 2)


def score_venue_coverage(constituents: pd.DataFrame) -> float:
    """0-100 score based on constituent completeness and ladder continuity."""
    if constituents.empty:
        return 0.0
    eligible = constituents[constituents["eligible"]] if "eligible" in constituents.columns else constituents
    if eligible.empty:
        return 0.0

    n_maturities = eligible["days_from_valuation"].nunique()
    n_eligible = len(eligible)

    # At least MIN_ELIGIBLE_CONSTITUENTS eligible quotes required for base coverage
    if n_eligible < MIN_ELIGIBLE_CONSTITUENTS:
        base = (n_eligible / MIN_ELIGIBLE_CONSTITUENTS) * 50.0
    else:
        base = 50.0

    # Ladder continuity: how many distinct maturity buckets?  6+ is full ladder
    ladder_score = min(50.0, (n_maturities / 6.0) * 50.0)

    # Gap penalty: large jumps in days_from_valuation reduce score
    days_sorted = sorted(eligible["days_from_valuation"].unique())
    if len(days_sorted) >= 2:
        gaps = [days_sorted[i + 1] - days_sorted[i] for i in range(len(days_sorted) - 1)]
        max_gap = max(gaps)
        # Gaps >90 days are concerning
        gap_penalty = min(15.0, max(0.0, (max_gap - 60) / 60.0 * 15.0))
    else:
        gap_penalty = 0.0

    return round(max(0.0, min(100.0, base + ladder_score - gap_penalty)), 2)


def score_venue_consistency(curve: pd.DataFrame) -> float:
    """0-100 score based on monotonicity, shape, and residuals."""
    if curve.empty or len(curve) < 2:
        return 50.0

    yoy = curve["expected_yoy_pct"].astype(float).values
    days = curve["days_from_valuation"].astype(float).values

    # Monotonicity check: what fraction of successive moves are same-direction?
    diffs = np.diff(yoy)
    if len(diffs) == 0:
        return 50.0
    positive_moves = np.sum(diffs >= 0)
    monotonicity_frac = float(positive_moves / len(diffs))
    # Penalty for non-monotonic moves: perfectly monotone -> 100, random -> ~50
    mono_score = monotonicity_frac * 100.0

    # Smoothness: penalise large jumps relative to overall range
    value_range = float(yoy.max() - yoy.min())
    if value_range > 0:
        max_jump = float(np.max(np.abs(diffs)))
        jump_ratio = max_jump / value_range
        smooth_score = max(0.0, (1.0 - jump_ratio) * 100.0)
    else:
        smooth_score = 80.0

    # Residuals: fit linear trend and check R-squared
    if len(days) >= 3:
        coeffs = np.polyfit(days, yoy, 1)
        fitted = np.polyval(coeffs, days)
        ss_res = float(np.sum((yoy - fitted) ** 2))
        ss_tot = float(np.sum((yoy - yoy.mean()) ** 2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        resid_score = max(0.0, r_squared * 100.0)
    else:
        resid_score = 60.0

    return round(0.40 * mono_score + 0.30 * smooth_score + 0.30 * resid_score, 2)


def compute_raw_venue_score(
    liquidity: float,
    spread: float,
    freshness: float,
    coverage: float,
    consistency: float,
    historical_calibration: float = 50.0,
) -> float:
    """Weighted composite venue score with explicit historical calibration input.

    Weights:
        0.25 liquidity
        0.15 spread
        0.15 freshness
        0.15 coverage
        0.10 consistency
        0.20 historical calibration
    """
    return round(
        0.25 * liquidity +
        0.15 * spread +
        0.15 * freshness +
        0.15 * coverage +
        0.10 * consistency +
        0.20 * historical_calibration,
        2,
    )


# ---------------------------------------------------------------------------
# 4.  Weighting engine V1
# ---------------------------------------------------------------------------

def compute_venue_weight_diagnostics(
    venue_name: str,
    requested_weight: float,
    constituents: pd.DataFrame,
    curve: pd.DataFrame,
    calibration_df: pd.DataFrame | None = None,
) -> VenueWeightDiagnostics:
    """Full diagnostic for one venue's weight computation, including Brier/log-loss calibration."""
    liq = score_venue_liquidity(constituents)
    spr = score_venue_spread_quality(constituents)
    frs = score_venue_freshness(constituents)
    cov = score_venue_coverage(constituents)
    con = score_venue_consistency(curve)
    if calibration_df is None:
        calibration_df = load_calibration_history()
    calibration_summary = compute_calibration_summary(calibration_df, venue_name, constituents)
    hist_cal = calibration_summary.historical_calibration_score
    raw = compute_raw_venue_score(liq, spr, frs, cov, con, hist_cal)

    eligible = True
    reason: str | None = None
    if cov < MIN_COVERAGE_SCORE:
        eligible = False
        reason = f"Coverage score {cov:.1f} below minimum {MIN_COVERAGE_SCORE}"
    elif con < MIN_CONSISTENCY_SCORE:
        eligible = False
        reason = f"Consistency score {con:.1f} below minimum {MIN_CONSISTENCY_SCORE}"
    elif hist_cal < MIN_HISTORICAL_CALIBRATION_SCORE:
        eligible = False
        reason = f"Historical calibration score {hist_cal:.1f} below minimum {MIN_HISTORICAL_CALIBRATION_SCORE}"
    elif len(constituents[constituents["eligible"]]) < MIN_ELIGIBLE_CONSTITUENTS:
        eligible = False
        reason = f"Only {len(constituents[constituents['eligible']])} eligible constituents (min {MIN_ELIGIBLE_CONSTITUENTS})"

    avg_weight = float(constituents["weight"].sum()) / max(len(constituents), 1)
    is_institutional = avg_weight > 0.15
    median_age = 25.0 if is_institutional else 90.0
    span = 15.0 if is_institutional else 45.0

    return VenueWeightDiagnostics(
        venue=venue_name,
        requested_weight=requested_weight,
        raw_venue_score=raw,
        raw_score_weight=0.0,
        effective_weight=0.0,
        eligible=eligible,
        eligibility_reason=reason,
        liquidity_score=liq,
        spread_quality_score=spr,
        freshness_score=frs,
        coverage_score=cov,
        internal_consistency_score=con,
        historical_calibration_score=calibration_summary.historical_calibration_score,
        brier_skill_score=calibration_summary.brier_skill_score,
        log_loss_skill_score=calibration_summary.log_loss_skill_score,
        calibration_bias_score=calibration_summary.calibration_bias_score,
        calibration_sample_size_score=calibration_summary.calibration_sample_size_score,
        calibration_sample_size=calibration_summary.calibration_sample_size,
        weighted_mean_brier_score=calibration_summary.weighted_mean_brier_score,
        weighted_mean_log_loss=calibration_summary.weighted_mean_log_loss,
        weighted_mean_abs_error_pct=calibration_summary.weighted_mean_abs_error_pct,
        weighted_bias_pct=calibration_summary.weighted_bias_pct,
        weighted_hit_rate=calibration_summary.weighted_hit_rate,
        calibration_methodology_note=calibration_summary.methodology_note,
        contract_family_calibration=calibration_summary.contract_family_breakdown,
        horizon_bucket_calibration=calibration_summary.horizon_bucket_breakdown,
        median_quote_age_seconds=median_age,
        snapshot_span_seconds=span,
    )


def compute_governed_blend_weights(
    kalshi_diag: VenueWeightDiagnostics,
    forecastex_diag: VenueWeightDiagnostics,
    blend_alpha: float = BLEND_ALPHA,
) -> tuple[float, float]:
    """Return (kalshi_effective, forecastex_effective) after score-blending and eligibility gating.

    Blend formula:
        effective_w = alpha * requested_w + (1 - alpha) * score_based_w
    where score_based_w is proportional to raw_venue_score.

    If a venue is ineligible, its effective weight is 0 and the other gets 100%.
    """
    both_eligible = kalshi_diag.eligible and forecastex_diag.eligible
    neither_eligible = not kalshi_diag.eligible and not forecastex_diag.eligible

    if neither_eligible:
        # Both ineligible: fall back to equal weight, flag for review
        kalshi_diag.raw_score_weight = 0.50
        forecastex_diag.raw_score_weight = 0.50
        kalshi_diag.effective_weight = 0.50
        forecastex_diag.effective_weight = 0.50
        return 0.50, 0.50

    if not both_eligible:
        # One venue ineligible
        if kalshi_diag.eligible:
            kalshi_diag.raw_score_weight = 1.0
            forecastex_diag.raw_score_weight = 0.0
            kalshi_diag.effective_weight = 1.0
            forecastex_diag.effective_weight = 0.0
            return 1.0, 0.0
        else:
            kalshi_diag.raw_score_weight = 0.0
            forecastex_diag.raw_score_weight = 1.0
            kalshi_diag.effective_weight = 0.0
            forecastex_diag.effective_weight = 1.0
            return 0.0, 1.0

    # Both eligible: score-based blending
    total_score = kalshi_diag.raw_venue_score + forecastex_diag.raw_venue_score
    if total_score <= 0:
        score_k = score_f = 0.50
    else:
        score_k = kalshi_diag.raw_venue_score / total_score
        score_f = forecastex_diag.raw_venue_score / total_score

    kalshi_diag.raw_score_weight = round(score_k, 4)
    forecastex_diag.raw_score_weight = round(score_f, 4)

    # Blend: alpha * requested + (1-alpha) * score-based
    eff_k = blend_alpha * kalshi_diag.requested_weight + (1.0 - blend_alpha) * score_k
    eff_f = blend_alpha * forecastex_diag.requested_weight + (1.0 - blend_alpha) * score_f

    # Normalise
    total_eff = eff_k + eff_f
    if total_eff <= 0:
        eff_k = eff_f = 0.50
    else:
        eff_k = eff_k / total_eff
        eff_f = eff_f / total_eff

    kalshi_diag.effective_weight = round(eff_k, 4)
    forecastex_diag.effective_weight = round(eff_f, 4)
    return round(eff_k, 4), round(eff_f, 4)


# ---------------------------------------------------------------------------
# 5.  Freshness attribution
# ---------------------------------------------------------------------------

def _simulated_quote_ages(n: int, is_institutional: bool, rng_seed: int = 42) -> np.ndarray:
    """Generate deterministic simulated quote ages in seconds."""
    rng = np.random.RandomState(rng_seed)
    if is_institutional:
        # Kalshi: tight cluster around 25s
        ages = rng.exponential(scale=25.0, size=n)
        ages = np.clip(ages, 2.0, 120.0)
    else:
        # ForecastEx: broader cluster around 90s
        ages = rng.exponential(scale=90.0, size=n)
        ages = np.clip(ages, 10.0, 400.0)
    return ages


def build_venue_freshness_summary(constituents: pd.DataFrame, venue: str) -> VenueFreshnessSummary:
    """Build freshness summary from constituent timestamps.

    Since demo constituent CSVs don't have real timestamps, simulate them:
    - Kalshi: median age ~25s, span ~15s (institutional, fast)
    - ForecastEx: median age ~90s, span ~45s (slower refresh)
    """
    n = len(constituents)
    if n == 0:
        return VenueFreshnessSummary(venue=venue)

    is_institutional = venue.lower() in ("kalshi",)
    seed = hash(venue) % (2**31)
    ages = _simulated_quote_ages(n, is_institutional, rng_seed=abs(seed))

    median_age = float(np.median(ages))
    max_age = float(np.max(ages))
    min_age = float(np.min(ages))
    stale_frac = float(np.mean(ages > STALE_QUOTE_SECONDS))
    fresh_frac = float(np.mean(ages <= FRESH_QUOTE_SECONDS))
    span = max_age - min_age

    return VenueFreshnessSummary(
        venue=venue,
        median_quote_age_seconds=round(median_age, 2),
        max_quote_age_seconds=round(max_age, 2),
        min_quote_age_seconds=round(min_age, 2),
        stale_quote_fraction=round(stale_frac, 4),
        fresh_quote_fraction=round(fresh_frac, 4),
        snapshot_span_seconds=round(span, 2),
    )


def build_blended_freshness_summary(
    kalshi_freshness: VenueFreshnessSummary,
    forecastex_freshness: VenueFreshnessSummary,
) -> BlendedFreshnessSummary:
    """Build blended freshness summary with cross-venue commentary."""
    now = datetime.now(timezone.utc)
    k_median = kalshi_freshness.median_quote_age_seconds
    f_median = forecastex_freshness.median_quote_age_seconds

    # Blended span: from earliest possible quote to now
    max_age = max(
        kalshi_freshness.max_quote_age_seconds,
        forecastex_freshness.max_quote_age_seconds,
    )
    min_age = min(
        kalshi_freshness.min_quote_age_seconds,
        forecastex_freshness.min_quote_age_seconds,
    )
    span = max_age - min_age

    blended = BlendedFreshnessSummary(
        blended_snapshot_start_utc=now.isoformat(),
        blended_snapshot_end_utc=now.isoformat(),
        blended_snapshot_span_seconds=round(span, 2),
        kalshi_snapshot_median_age_seconds=round(k_median, 2),
        forecastex_snapshot_median_age_seconds=round(f_median, 2),
        cross_venue_median_age_gap_seconds=round(abs(k_median - f_median), 2),
        freshness_commentary="",
    )
    blended.freshness_commentary = generate_freshness_commentary(blended)
    return blended


def generate_freshness_commentary(blended: BlendedFreshnessSummary) -> str:
    """Generate human-readable freshness commentary string."""
    parts: list[str] = []

    k_age = blended.kalshi_snapshot_median_age_seconds
    f_age = blended.forecastex_snapshot_median_age_seconds
    gap = blended.cross_venue_median_age_gap_seconds

    # Kalshi assessment
    if k_age <= FRESH_QUOTE_SECONDS:
        parts.append(f"Kalshi quotes are fresh (median age {k_age:.0f}s)")
    elif k_age <= STALE_QUOTE_SECONDS:
        parts.append(f"Kalshi quotes are aging (median age {k_age:.0f}s)")
    else:
        parts.append(f"Kalshi quotes are STALE (median age {k_age:.0f}s)")

    # ForecastEx assessment
    if f_age <= FRESH_QUOTE_SECONDS:
        parts.append(f"ForecastEx quotes are fresh (median age {f_age:.0f}s)")
    elif f_age <= STALE_QUOTE_SECONDS:
        parts.append(f"ForecastEx quotes are aging (median age {f_age:.0f}s)")
    else:
        parts.append(f"ForecastEx quotes are STALE (median age {f_age:.0f}s)")

    # Cross-venue gap
    if gap > 120:
        parts.append(f"Cross-venue age gap is wide ({gap:.0f}s) — consider timing alignment")
    elif gap > 60:
        parts.append(f"Cross-venue age gap is moderate ({gap:.0f}s)")
    else:
        parts.append(f"Cross-venue age gap is tight ({gap:.0f}s)")

    # Overall
    span = blended.blended_snapshot_span_seconds
    if span <= 60:
        parts.append("Blended snapshot window is tight")
    elif span <= 180:
        parts.append("Blended snapshot window is acceptable")
    else:
        parts.append(f"Blended snapshot window is wide ({span:.0f}s) — may reduce confidence")

    return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# 6.  FalconX credibility hardening: explicit microstructure, smoothing,
#     calibration, confidence bands, and trade framing.
# ---------------------------------------------------------------------------

MICROSTRUCTURE_MAX_PROXY_SPREAD_BP = 35.0
MICROSTRUCTURE_FRESH_QUOTE_SECONDS = 60.0
MICROSTRUCTURE_STALE_QUOTE_SECONDS = 300.0
CONFIDENCE_HIGH_THRESHOLD = 80.0
CONFIDENCE_REVIEW_THRESHOLD = 65.0


@dataclass
class SmoothingDiagnostics:
    method_requested: str
    method_used: str
    monotone_direction: str
    anchor_count: int
    coverage_ratio: float
    max_residual_bp: float
    rmse_bp: float
    notes: list[str]


@dataclass
class TradeIdea:
    title: str
    expression: str
    rationale: str
    trigger: str
    risk_note: str


def apply_microstructure_filters(constituents: pd.DataFrame, venue_name: str) -> pd.DataFrame:
    """Attach explicit quote-quality proxies and filter the constituent set.

    The uploaded demo CSVs do not carry live bid/ask/depth/timestamp fields, so this
    method derives deterministic proxy fields from available constituent statistics.
    These fields are named explicitly so the developer can replace them 1:1 with live
    quote inputs later without changing downstream logic.
    """
    if constituents.empty:
        work = constituents.copy()
        for col in [
            'proxy_spread_bp', 'proxy_quote_age_seconds', 'quote_quality_score',
            'passes_spread_filter', 'passes_staleness_filter', 'included_in_curve',
            'quote_selection_reason',
        ]:
            work[col] = []
        return work

    work = constituents.copy()
    venue_l = (venue_name or '').lower()
    venue_bias = 0.85 if 'kalshi' in venue_l else 1.10
    weight_rank = work['weight'].astype(float).rank(method='dense', pct=True)
    dispersion_bp = work['std_dev_pct'].astype(float).abs() * 100.0
    work['proxy_spread_bp'] = (dispersion_bp * 6.0 * venue_bias).clip(lower=3.0, upper=80.0)
    work['proxy_quote_age_seconds'] = (
        (1.0 - weight_rank) * (140.0 if 'kalshi' in venue_l else 220.0)
        + work['proxy_spread_bp'] * (1.5 if 'kalshi' in venue_l else 2.25)
        + (work['days_from_valuation'].astype(float) / 180.0) * 20.0
    ).round(2)
    work['passes_spread_filter'] = work['proxy_spread_bp'] <= MICROSTRUCTURE_MAX_PROXY_SPREAD_BP
    work['passes_staleness_filter'] = work['proxy_quote_age_seconds'] <= MICROSTRUCTURE_STALE_QUOTE_SECONDS
    work['quote_quality_score'] = (
        0.45 * (100.0 - work['proxy_spread_bp'].clip(upper=100.0))
        + 0.35 * (100.0 - (work['proxy_quote_age_seconds'] / MICROSTRUCTURE_STALE_QUOTE_SECONDS * 100.0).clip(upper=100.0))
        + 0.20 * (work['weight'].astype(float) * 100.0).clip(upper=100.0)
    ).round(2)
    work['included_in_curve'] = work['eligible'].astype(bool) & work['passes_spread_filter'] & work['passes_staleness_filter']

    reasons = []
    for _, row in work.iterrows():
        if bool(row['included_in_curve']):
            if row['proxy_spread_bp'] <= 12 and row['proxy_quote_age_seconds'] <= MICROSTRUCTURE_FRESH_QUOTE_SECONDS:
                reasons.append('mid_selected_tight_and_fresh')
            elif row['proxy_spread_bp'] <= MICROSTRUCTURE_MAX_PROXY_SPREAD_BP:
                reasons.append('mid_selected_with_guardrails')
            else:
                reasons.append('fallback_last_trade_proxy')
        else:
            if not bool(row['passes_spread_filter']):
                reasons.append('excluded_wide_proxy_spread')
            elif not bool(row['passes_staleness_filter']):
                reasons.append('excluded_stale_proxy_quote')
            else:
                reasons.append('excluded_ineligible')
    work['quote_selection_reason'] = reasons
    return work


def _weighted_isotonic(values: np.ndarray, weights: np.ndarray, increasing: bool = True) -> np.ndarray:
    """Simple weighted PAVA implementation for monotone smoothing."""
    y = values.astype(float).copy()
    w = weights.astype(float).copy()
    if not increasing:
        y = -y
    blocks = []
    for yi, wi in zip(y, w):
        blocks.append([yi, wi, 1])
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
            y1, w1, c1 = blocks[-2]
            y2, w2, c2 = blocks[-1]
            new_w = w1 + w2
            new_y = (y1 * w1 + y2 * w2) / max(new_w, 1e-12)
            blocks[-2:] = [[new_y, new_w, c1 + c2]]
    out = []
    for val, _, count in blocks:
        out.extend([val] * count)
    arr = np.array(out, dtype=float)
    if not increasing:
        arr = -arr
    return arr


def smooth_reference_curve(
    curve: pd.DataFrame,
    constituents: pd.DataFrame | None = None,
    method: str = 'liquidity_weighted_monotone_linear',
    fallback_method: str = 'nelson_siegel_proxy',
) -> tuple[pd.DataFrame, SmoothingDiagnostics]:
    """Apply an explicit smoothing pass and return diagnostics.

    Primary method: liquidity-weighted monotone linear smoothing.
    Fallback method: low-order parametric proxy (quadratic fit labelled Nelson-Siegel proxy)
    when coverage is sparse.
    """
    if curve.empty:
        return curve.copy(), SmoothingDiagnostics(method, method, 'flat', 0, 0.0, 0.0, 0.0, ['Empty curve'])

    work = curve.sort_values('days_from_valuation').reset_index(drop=True).copy()
    raw = work['expected_yoy_pct'].astype(float).to_numpy()
    x = work['days_from_valuation'].astype(float).to_numpy()

    if constituents is not None and not constituents.empty and 'included_in_curve' in constituents.columns:
        weight_map = constituents[constituents['included_in_curve']].groupby('days_from_valuation')['weight'].sum().to_dict()
        weights = np.array([max(float(weight_map.get(int(day), 0.0)), 0.05) for day in x], dtype=float)
        coverage_ratio = float(len(weight_map) / max(len(work), 1))
    else:
        weights = np.ones(len(work), dtype=float)
        coverage_ratio = 1.0

    direction = 'increasing' if raw[-1] >= raw[0] else 'decreasing'
    notes = []
    if len(work) < 4 or coverage_ratio < 0.60:
        deg = 2 if len(work) >= 3 else 1
        coeffs = np.polyfit(x, raw, deg=deg, w=np.sqrt(weights))
        smoothed = np.polyval(coeffs, x)
        method_used = fallback_method
        notes.append('Sparse maturity coverage triggered parametric fallback.')
    else:
        smoothed = _weighted_isotonic(raw, weights, increasing=(direction == 'increasing'))
        # small linear blend back toward raw to preserve local shape without breaking monotonicity materially
        smoothed = 0.75 * smoothed + 0.25 * raw
        method_used = method
        notes.append('Primary monotone smoother applied to liquidity-weighted anchors.')

    residual_bp = (raw - smoothed) * 100.0
    work['expected_yoy_raw_pct'] = raw
    work['expected_yoy_pct'] = np.round(smoothed, 6)
    work['smoothing_residual_bp'] = np.round(residual_bp, 2)
    work['smoothing_method_used'] = method_used
    work['curve_shape_flag'] = direction

    rmse_bp = float(np.sqrt(np.mean(np.square(residual_bp)))) if len(residual_bp) else 0.0
    max_residual_bp = float(np.max(np.abs(residual_bp))) if len(residual_bp) else 0.0
    diag = SmoothingDiagnostics(
        method_requested=method,
        method_used=method_used,
        monotone_direction=direction,
        anchor_count=int(len(work)),
        coverage_ratio=round(coverage_ratio, 4),
        max_residual_bp=round(max_residual_bp, 2),
        rmse_bp=round(rmse_bp, 2),
        notes=notes,
    )
    return work, diag


def compute_weight_calibration_summary(
    kalshi_diag: VenueWeightDiagnostics,
    forecastex_diag: VenueWeightDiagnostics,
    blend_alpha: float = BLEND_ALPHA,
) -> dict:
    total_score = kalshi_diag.raw_venue_score + forecastex_diag.raw_venue_score
    score_k = kalshi_diag.raw_venue_score / total_score if total_score > 0 else 0.5
    score_f = forecastex_diag.raw_venue_score / total_score if total_score > 0 else 0.5
    return {
        'blend_alpha': round(blend_alpha, 3),
        'score_weight_share_kalshi': round(score_k, 4),
        'score_weight_share_forecastex': round(score_f, 4),
        'requested_weight_share_kalshi': round(kalshi_diag.requested_weight, 4),
        'requested_weight_share_forecastex': round(forecastex_diag.requested_weight, 4),
        'effective_weight_share_kalshi': round(kalshi_diag.effective_weight, 4),
        'effective_weight_share_forecastex': round(forecastex_diag.effective_weight, 4),
        'kalshi_historical_calibration_score': round(kalshi_diag.historical_calibration_score, 2),
        'forecastex_historical_calibration_score': round(forecastex_diag.historical_calibration_score, 2),
        'kalshi_weighted_mean_brier_score': round(kalshi_diag.weighted_mean_brier_score, 4),
        'forecastex_weighted_mean_brier_score': round(forecastex_diag.weighted_mean_brier_score, 4),
        'kalshi_calibration_sample_size': int(kalshi_diag.calibration_sample_size),
        'forecastex_calibration_sample_size': int(forecastex_diag.calibration_sample_size),
        'calibration_rule': 'effective_w = alpha*requested_w + (1-alpha)*score_w, subject to eligibility gating; raw score now includes historical calibration.',
    }


def compute_enhanced_publishability(
    curve: pd.DataFrame,
    blend_metadata: BlendMetadata,
    kalshi_diag: VenueWeightDiagnostics | None = None,
    forecastex_diag: VenueWeightDiagnostics | None = None,
    blended_freshness: BlendedFreshnessSummary | None = None,
) -> tuple[str, str, float, dict]:
    maturity_score = min(100.0, float(curve['days_from_valuation'].max()) / float(SIX_MONTH_DAYS) * 100.0)
    source_score = 100.0 if (blend_metadata.kalshi_eligible and blend_metadata.forecastex_eligible) else 70.0 if (blend_metadata.kalshi_eligible or blend_metadata.forecastex_eligible) else 0.0
    balance_score = max(0.0, 100.0 - abs(blend_metadata.effective_kalshi_weight - blend_metadata.effective_forecastex_weight) * 100.0)
    quality_scores = []
    for diag in [kalshi_diag, forecastex_diag]:
        if diag is not None and diag.eligible:
            quality_scores.append((diag.raw_venue_score + diag.coverage_score + diag.internal_consistency_score) / 3.0)
    quality_score = float(np.mean(quality_scores)) if quality_scores else 0.0
    if blended_freshness is not None:
        age_penalty = min(40.0, blended_freshness.cross_venue_median_age_gap_seconds / 3.0)
        freshness_score = max(0.0, 100.0 - age_penalty - max(0.0, blended_freshness.blended_snapshot_span_seconds - 60.0) / 4.0)
    else:
        freshness_score = 75.0
    calibration_scores = []
    for diag in [kalshi_diag, forecastex_diag]:
        if diag is not None and diag.eligible:
            calibration_scores.append(diag.historical_calibration_score)
    calibration_score = float(np.mean(calibration_scores)) if calibration_scores else 50.0

    confidence_score = round(
        0.20 * maturity_score +
        0.15 * source_score +
        0.10 * balance_score +
        0.20 * quality_score +
        0.20 * freshness_score +
        0.15 * calibration_score,
        2,
    )
    if confidence_score >= CONFIDENCE_HIGH_THRESHOLD:
        publishability, confidence = 'Eligible', 'High'
    elif confidence_score >= CONFIDENCE_REVIEW_THRESHOLD:
        publishability, confidence = 'Review', 'Moderate'
    else:
        publishability, confidence = 'Draft', 'Low'
    breakdown = {
        'maturity_score': round(maturity_score, 2),
        'source_score': round(source_score, 2),
        'balance_score': round(balance_score, 2),
        'quality_score': round(quality_score, 2),
        'freshness_score': round(freshness_score, 2),
        'calibration_score': round(calibration_score, 2),
        'high_threshold': CONFIDENCE_HIGH_THRESHOLD,
        'review_threshold': CONFIDENCE_REVIEW_THRESHOLD,
    }
    return publishability, confidence, confidence_score, breakdown


def generate_trade_ideas(
    snapshot: Tier1Snapshot,
    curve: pd.DataFrame,
    kalshi_diag: VenueWeightDiagnostics | None = None,
    forecastex_diag: VenueWeightDiagnostics | None = None,
) -> list[TradeIdea]:
    ideas: list[TradeIdea] = []
    direction = 'steepener' if snapshot.term_structure_pct > 0 else 'flattener'
    venue_edge = 'Kalshi' if (kalshi_diag and forecastex_diag and kalshi_diag.raw_venue_score >= forecastex_diag.raw_venue_score) else 'ForecastEx'
    opposite = 'ForecastEx' if venue_edge == 'Kalshi' else 'Kalshi'
    basis_dir = 'short perp / long reference' if snapshot.basis_bp > 0 else 'long perp / short reference'

    ideas.append(TradeIdea(
        title='Perp vs Oriel Fair Value basis trade',
        expression=basis_dir,
        rationale=f'Perp basis is {snapshot.basis_bp:+.1f} bp versus Oriel FV, creating a direct convergence expression.',
        trigger='Trigger when perp/FV gap exceeds desk threshold and confidence remains Review-or-better.',
        risk_note='Risk is persistence in exchange-specific funding or collateral distortions.',
    ))
    ideas.append(TradeIdea(
        title=f'Front-end CPI curve {direction}',
        expression=f'Long 6M implied / short 1M implied ({direction})',
        rationale=f'Term structure is {snapshot.term_structure_pct:+.2f}% from 1M to 6M, which can be isolated as a curve slope trade.',
        trigger='Use when slope diverges from OTC breakeven slope or macro catalysts cluster in the front end.',
        risk_note='Risk is parallel repricing of the entire curve rather than slope normalization.',
    ))
    ideas.append(TradeIdea(
        title='Venue quality relative-value overlay',
        expression=f'Lean on {venue_edge} for price discovery, fade {opposite} where residuals widen',
        rationale='Governed weighting highlights the cleaner venue and turns cross-venue dispersion into an execution signal.',
        trigger='Best when venue diagnostics show persistent score and freshness separation but both venues remain eligible.',
        risk_note='Risk is asynchronous quote refresh creating false residuals; use timestamp commentary and staleness gates.',
    ))
    return ideas
