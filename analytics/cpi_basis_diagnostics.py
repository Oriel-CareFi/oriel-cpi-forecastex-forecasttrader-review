from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass
class DiagnosticsArtifacts:
    contract_level: pd.DataFrame
    maturity_level: pd.DataFrame
    venue_comparison: pd.DataFrame
    summary: dict
    scenario_tests: pd.DataFrame
    metadata: dict


REQUIRED_BASE_COLS = [
    "target_month",
    "days_from_valuation",
    "constituent_id",
    "weight",
    "eligible",
    "expected_yoy_pct",
    "std_dev_pct",
]


def _ensure_datetime(series: pd.Series) -> pd.Series:
    out = pd.to_datetime(series, errors="coerce")
    if out.isna().all():
        return pd.to_datetime(pd.Timestamp.utcnow().floor("min"))
    return out



def _bounded(series: pd.Series, lo: float = 0.0, hi: float = 1.0) -> pd.Series:
    return series.clip(lower=lo, upper=hi)



def _norm(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)
    if s.nunique(dropna=False) <= 1:
        base = pd.Series(np.ones(len(s)) * 0.5, index=s.index)
    else:
        base = (s - s.min()) / (s.max() - s.min())
    return _bounded(base if higher_is_better else 1.0 - base)



def _synthesize_quote_fields(df: pd.DataFrame, venue: str) -> pd.DataFrame:
    out = df.copy()
    venue_depth_mult = 1.10 if venue.lower().startswith("kal") else 0.92
    venue_oi_mult = 1.18 if venue.lower().startswith("kal") else 0.86
    venue_recency_mult = 0 if venue.lower().startswith("kal") else 4
    base_time = pd.Timestamp.utcnow().floor("min")

    # Derived / proxy fields only fill gaps; if live fields exist they are preserved.
    spread_bp_proxy = (
        3.0
        + out["std_dev_pct"].astype(float) * 18.0
        + (1.0 - out["weight"].astype(float).clip(lower=0.0, upper=1.0)) * 6.0
        + (out["days_from_valuation"].astype(float) / max(1.0, out["days_from_valuation"].max())) * 4.0
    )
    out["spread_bp"] = pd.to_numeric(out["spread_bp"], errors="coerce").fillna(spread_bp_proxy) if "spread_bp" in out.columns else spread_bp_proxy

    depth_proxy = (
        1200.0
        * venue_depth_mult
        * (0.45 + out["weight"].astype(float).clip(lower=0.05))
        / (1.0 + out["std_dev_pct"].astype(float) * 2.5)
    )
    out["depth_size"] = pd.to_numeric(out["depth_size"], errors="coerce").fillna(depth_proxy.round(0)) if "depth_size" in out.columns else depth_proxy.round(0)

    oi_proxy = (
        900.0
        * venue_oi_mult
        * (0.55 + out["weight"].astype(float).clip(lower=0.05))
        * (1.0 + out["days_from_valuation"].astype(float) / max(30.0, out["days_from_valuation"].max()))
    )
    out["open_interest"] = pd.to_numeric(out["open_interest"], errors="coerce").fillna(oi_proxy.round(0)) if "open_interest" in out.columns else oi_proxy.round(0)

    volume_proxy = (out["open_interest"].astype(float) * (0.10 + out["weight"].astype(float) * 0.18)).round(0)
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(volume_proxy) if "volume" in out.columns else volume_proxy

    if "last_update_time" in out.columns:
        out["last_update_time"] = _ensure_datetime(out["last_update_time"])
    else:
        out["last_update_time"] = [
            base_time - pd.Timedelta(minutes=int(2 + venue_recency_mult + i % 5 + (d / 45.0)))
            for i, d in enumerate(out["days_from_valuation"].astype(float))
        ]

    out["raw_contract_implied_expected_cpi"] = (
        pd.to_numeric(out["raw_contract_implied_expected_cpi"], errors="coerce").fillna(out["expected_yoy_pct"].astype(float))
        if "raw_contract_implied_expected_cpi" in out.columns else out["expected_yoy_pct"].astype(float)
    )

    out["bid_size"] = pd.to_numeric(out["bid_size"], errors="coerce").fillna((out["depth_size"] * 0.48).round(0)) if "bid_size" in out.columns else (out["depth_size"] * 0.48).round(0)
    out["ask_size"] = pd.to_numeric(out["ask_size"], errors="coerce").fillna((out["depth_size"] * 0.52).round(0)) if "ask_size" in out.columns else (out["depth_size"] * 0.52).round(0)
    out["has_live_quote_fields"] = bool(
        {"spread_bp", "depth_size", "open_interest", "last_update_time"}.issubset(set(df.columns))
    )
    return out



def _confidence_components(contract_df: pd.DataFrame) -> pd.DataFrame:
    out = contract_df.copy()
    now = pd.Timestamp.utcnow().floor("min")
    out["minutes_since_update"] = ((now - pd.to_datetime(out["last_update_time"])) / pd.Timedelta(minutes=1)).astype(float)

    spread_q = _norm(out["spread_bp"], higher_is_better=False)
    depth_q = _norm(out["depth_size"], higher_is_better=True)
    oi_q = _norm(out["open_interest"], higher_is_better=True)
    freshness_q = _norm(out["minutes_since_update"], higher_is_better=False)

    # Coverage is proxied at the contract level by contribution weight and eligibility.
    coverage_q = _bounded(0.35 + out["weight"].astype(float).clip(lower=0.0, upper=1.0) * 0.65)
    eligibility_q = np.where(out["eligible"].astype(bool), 1.0, 0.55)

    out["spread_quality"] = spread_q
    out["depth_quality"] = depth_q
    out["oi_quality"] = oi_q
    out["freshness_quality"] = freshness_q
    out["coverage_quality"] = coverage_q
    out["confidence_score"] = (
        0.30 * spread_q
        + 0.25 * depth_q
        + 0.20 * oi_q
        + 0.15 * freshness_q
        + 0.10 * coverage_q
    ) * eligibility_q
    out["confidence_score"] = _bounded(out["confidence_score"]) * 100.0
    return out



def prepare_contract_level(constituents: pd.DataFrame, venue: str) -> pd.DataFrame:
    missing = [c for c in REQUIRED_BASE_COLS if c not in constituents.columns]
    if missing:
        raise ValueError(f"Missing required constituent columns for diagnostics: {missing}")

    df = constituents.copy()
    df["venue"] = venue
    df["target_month"] = pd.to_datetime(df["target_month"])
    df["eligible"] = df["eligible"].astype(bool)
    df = _synthesize_quote_fields(df, venue)
    df = _confidence_components(df)
    return df.sort_values(["target_month", "constituent_id"]).reset_index(drop=True)



def aggregate_maturity_metrics(contract_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (venue, target_month, days), grp in contract_df.groupby(["venue", "target_month", "days_from_valuation"], sort=True):
        elig = grp[grp["eligible"]].copy()
        use = elig if not elig.empty else grp.copy()
        weights = use["weight"].astype(float)
        if weights.sum() <= 0:
            weights = pd.Series(np.ones(len(use)), index=use.index, dtype=float)
        weights = weights / weights.sum()

        rows.append(
            {
                "venue": venue,
                "target_month": pd.Timestamp(target_month),
                "days_from_valuation": int(days),
                "raw_contract_implied_expected_cpi": float(np.average(use["raw_contract_implied_expected_cpi"], weights=weights)),
                "bid_ask_spread_bp": float(np.average(use["spread_bp"], weights=weights)),
                "depth_size": float(np.average(use["depth_size"], weights=weights)),
                "open_interest": float(np.average(use["open_interest"], weights=weights)),
                "volume": float(np.average(use["volume"], weights=weights)),
                "last_update_time": pd.to_datetime(use["last_update_time"]).max(),
                "minutes_since_update": float(np.average(use["minutes_since_update"], weights=weights)),
                "confidence_score": float(np.average(use["confidence_score"], weights=weights)),
                "n_contracts": int(len(use)),
                "eligible_contracts": int(use["eligible"].sum()),
                "has_live_quote_fields": bool(use["has_live_quote_fields"].all()),
            }
        )

    out = pd.DataFrame(rows).sort_values(["days_from_valuation", "venue"]).reset_index(drop=True)
    return out



def build_venue_comparison(maturity_df: pd.DataFrame) -> pd.DataFrame:
    pivot = maturity_df.pivot_table(
        index=["target_month", "days_from_valuation"],
        columns="venue",
        values=[
            "raw_contract_implied_expected_cpi",
            "bid_ask_spread_bp",
            "depth_size",
            "open_interest",
            "minutes_since_update",
            "confidence_score",
        ],
        aggfunc="first",
    )
    pivot.columns = [f"{c[1].lower()}_{c[0]}" for c in pivot.columns]
    pivot = pivot.reset_index()

    if {
        "kalshi_raw_contract_implied_expected_cpi",
        "forecastex_raw_contract_implied_expected_cpi",
    }.issubset(pivot.columns):
        pivot["abs_curve_diff_bp"] = (
            pivot["kalshi_raw_contract_implied_expected_cpi"]
            - pivot["forecastex_raw_contract_implied_expected_cpi"]
        ).abs() * 100.0
    else:
        pivot["abs_curve_diff_bp"] = np.nan

    conf_cols = [c for c in pivot.columns if c.endswith("confidence_score")]
    spread_cols = [c for c in pivot.columns if c.endswith("bid_ask_spread_bp")]
    pivot["avg_confidence_score"] = pivot[conf_cols].mean(axis=1)
    pivot["avg_spread_bp"] = pivot[spread_cols].mean(axis=1)

    # Liquidity weakness flag: low confidence / wide spread / shallow depth.
    def _liquidity_flag(row: pd.Series) -> str:
        if row.get("avg_confidence_score", 0) < 55:
            return "Low confidence"
        if row.get("avg_spread_bp", 0) > 10:
            return "Wide spreads"
        return "Healthy"

    pivot["liquidity_flag"] = pivot.apply(_liquidity_flag, axis=1)
    return pivot.sort_values("days_from_valuation").reset_index(drop=True)



def _scenario_curve(contract_df: pd.DataFrame, spread_threshold_bp: float | None, stale_after_min: int | None, weighting: str) -> pd.DataFrame:
    work = contract_df.copy()
    if spread_threshold_bp is not None:
        work = work[work["spread_bp"] <= float(spread_threshold_bp)].copy()
    if stale_after_min is not None:
        work = work[work["minutes_since_update"] <= float(stale_after_min)].copy()
    if work.empty:
        return pd.DataFrame(columns=["venue", "target_month", "days_from_valuation", "expected_cpi_pct"])

    rows = []
    for (venue, target_month, days), grp in work.groupby(["venue", "target_month", "days_from_valuation"], sort=True):
        elig = grp[grp["eligible"]].copy()
        use = elig if not elig.empty else grp.copy()
        if weighting == "confidence":
            weights = use["confidence_score"].astype(float)
        else:
            weights = use["weight"].astype(float)
        if weights.sum() <= 0:
            weights = pd.Series(np.ones(len(use)), index=use.index, dtype=float)
        weights = weights / weights.sum()
        rows.append(
            {
                "venue": venue,
                "target_month": pd.Timestamp(target_month),
                "days_from_valuation": int(days),
                "expected_cpi_pct": float(np.average(use["raw_contract_implied_expected_cpi"], weights=weights)),
            }
        )
    return pd.DataFrame(rows)



def _scenario_dispersion(contract_df: pd.DataFrame, spread_threshold_bp: float | None = None, stale_after_min: int | None = None, weighting: str = "equal") -> tuple[float, int]:
    curve = _scenario_curve(contract_df, spread_threshold_bp, stale_after_min, weighting)
    if curve.empty:
        return np.nan, 0
    pivot = curve.pivot_table(index=["target_month", "days_from_valuation"], columns="venue", values="expected_cpi_pct", aggfunc="first")
    if not {"Kalshi", "ForecastEx"}.issubset(pivot.columns):
        return np.nan, int(len(pivot))
    diff_bp = (pivot["Kalshi"] - pivot["ForecastEx"]).abs() * 100.0
    return float(diff_bp.mean()), int(diff_bp.notna().sum())



def build_scenario_tests(contract_df: pd.DataFrame, spread_threshold_bp: float = 8.0, stale_after_min: int = 15) -> pd.DataFrame:
    baseline_disp, baseline_n = _scenario_dispersion(contract_df, None, None, "equal")
    spread_disp, spread_n = _scenario_dispersion(contract_df, spread_threshold_bp, None, "equal")
    stale_disp, stale_n = _scenario_dispersion(contract_df, None, stale_after_min, "equal")
    conf_disp, conf_n = _scenario_dispersion(contract_df, None, None, "confidence")

    rows = [
        {
            "test": "Baseline",
            "rule": "All eligible quotes, equal constituent weights",
            "avg_dispersion_bp": baseline_disp,
            "coverage_maturities": baseline_n,
            "delta_vs_baseline_bp": 0.0,
        },
        {
            "test": "Spread filter",
            "rule": f"Use quotes only when bid/ask spread ≤ {spread_threshold_bp:.1f} bp",
            "avg_dispersion_bp": spread_disp,
            "coverage_maturities": spread_n,
            "delta_vs_baseline_bp": None if pd.isna(spread_disp) or pd.isna(baseline_disp) else spread_disp - baseline_disp,
        },
        {
            "test": "Drop stale quotes",
            "rule": f"Exclude quotes older than {stale_after_min:d} minutes",
            "avg_dispersion_bp": stale_disp,
            "coverage_maturities": stale_n,
            "delta_vs_baseline_bp": None if pd.isna(stale_disp) or pd.isna(baseline_disp) else stale_disp - baseline_disp,
        },
        {
            "test": "Confidence weighted",
            "rule": "Reweight constituents by confidence score rather than equally",
            "avg_dispersion_bp": conf_disp,
            "coverage_maturities": conf_n,
            "delta_vs_baseline_bp": None if pd.isna(conf_disp) or pd.isna(baseline_disp) else conf_disp - baseline_disp,
        },
    ]
    out = pd.DataFrame(rows)
    return out



def summarize_findings(venue_comparison: pd.DataFrame, scenario_tests: pd.DataFrame) -> dict:
    vc = venue_comparison.copy()
    vc["least_liquid"] = (vc["avg_confidence_score"] < vc["avg_confidence_score"].median()).astype(int)
    vc["high_dispersion"] = (vc["abs_curve_diff_bp"] >= vc["abs_curve_diff_bp"].median()).astype(int)
    concentration_share = float(vc.loc[vc["least_liquid"] == 1, "high_dispersion"].sum() / max(1, vc["high_dispersion"].sum()))
    corr = vc[["abs_curve_diff_bp", "avg_confidence_score"]].corr().iloc[0, 1] if len(vc) >= 2 else np.nan

    baseline = scenario_tests.loc[scenario_tests["test"] == "Baseline", "avg_dispersion_bp"].iloc[0]
    spread = scenario_tests.loc[scenario_tests["test"] == "Spread filter", "avg_dispersion_bp"].iloc[0]
    stale = scenario_tests.loc[scenario_tests["test"] == "Drop stale quotes", "avg_dispersion_bp"].iloc[0]
    conf = scenario_tests.loc[scenario_tests["test"] == "Confidence weighted", "avg_dispersion_bp"].iloc[0]

    def _narrows(x: float, base: float) -> bool | None:
        if pd.isna(x) or pd.isna(base):
            return None
        return bool(x < base)

    return {
        "avg_dispersion_bp": float(vc["abs_curve_diff_bp"].mean()) if len(vc) else np.nan,
        "max_dispersion_bp": float(vc["abs_curve_diff_bp"].max()) if len(vc) else np.nan,
        "dispersion_concentrated_in_least_liquid": concentration_share >= 0.60,
        "least_liquid_high_dispersion_share": concentration_share,
        "dispersion_confidence_correlation": corr,
        "spread_filter_narrows_gap": _narrows(spread, baseline),
        "drop_stale_narrows_gap": _narrows(stale, baseline),
        "confidence_weighting_narrows_gap": _narrows(conf, baseline),
        "baseline_dispersion_bp": baseline,
        "spread_filtered_dispersion_bp": spread,
        "stale_filtered_dispersion_bp": stale,
        "confidence_weighted_dispersion_bp": conf,
    }



def build_diagnostics(
    kalshi_constituents: pd.DataFrame,
    forecastex_constituents: pd.DataFrame,
    *,
    spread_threshold_bp: float = 8.0,
    stale_after_min: int = 15,
) -> DiagnosticsArtifacts:
    k_contracts = prepare_contract_level(kalshi_constituents, "Kalshi")
    f_contracts = prepare_contract_level(forecastex_constituents, "ForecastEx")
    contract_df = pd.concat([k_contracts, f_contracts], ignore_index=True)
    maturity_df = aggregate_maturity_metrics(contract_df)
    venue_comparison = build_venue_comparison(maturity_df)
    scenario_tests = build_scenario_tests(contract_df, spread_threshold_bp, stale_after_min)
    summary = summarize_findings(venue_comparison, scenario_tests)
    metadata = {
        "uses_live_quote_fields": bool(contract_df["has_live_quote_fields"].all()),
        "spread_threshold_bp": float(spread_threshold_bp),
        "stale_after_min": int(stale_after_min),
    }
    return DiagnosticsArtifacts(
        contract_level=contract_df,
        maturity_level=maturity_df,
        venue_comparison=venue_comparison,
        summary=summary,
        scenario_tests=scenario_tests,
        metadata=metadata,
    )
