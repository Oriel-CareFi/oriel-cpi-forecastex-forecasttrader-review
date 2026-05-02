from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Iterable

import math
import numpy as np
import pandas as pd

from engine import MaturitySnapshot, BinaryThresholdContract, ExactOutcomeContract

_NORMAL = NormalDist()


@dataclass
class VolSurfaceArtifacts:
    implied_vol: pd.DataFrame
    scenario_grid: pd.DataFrame
    component_surface: pd.DataFrame
    summary: dict


def _ttm_years(maturity: pd.Timestamp | object, valuation_date: pd.Timestamp | object) -> float:
    m = pd.Timestamp(maturity)
    v = pd.Timestamp(valuation_date)
    return max((m - v).days / 365.25, 1.0 / 365.25)


def _safe_inv_cdf(p: float) -> float:
    clipped = min(max(float(p), 1e-6), 1.0 - 1e-6)
    return _NORMAL.inv_cdf(clipped)


def _binary_sigma_from_forward(forward_pct: float, threshold: float, price: float, ttm_years: float) -> float | None:
    """Approximate implied sigma for a digital call: P[X > K] = N((F-K)/(sigma*sqrt(T)))."""
    if ttm_years <= 0:
        return None
    p = min(max(float(price), 0.001), 0.999)
    z = _safe_inv_cdf(p)
    if abs(z) < 1e-4:
        return None
    sigma = abs((forward_pct - float(threshold)) / (z * math.sqrt(ttm_years)))
    if not math.isfinite(sigma):
        return None
    return float(max(sigma, 0.01))


def _pmf_sigma(snapshot: MaturitySnapshot) -> float | None:
    if not snapshot.exact_outcomes:
        return None
    values = np.array([float(c.value) for c in snapshot.exact_outcomes], dtype=float)
    probs = np.array([max(float(c.price), 0.0) for c in snapshot.exact_outcomes], dtype=float)
    if probs.sum() <= 0:
        return None
    probs = probs / probs.sum()
    mu = float(np.sum(values * probs))
    var = float(np.sum(probs * ((values - mu) ** 2)))
    return max(var ** 0.5, 0.01)


def build_binary_implied_vol_surface(
    snapshots: Iterable[MaturitySnapshot],
    parent_curve: pd.DataFrame,
    valuation_date: pd.Timestamp,
) -> pd.DataFrame:
    curve = parent_curve.copy()
    curve["target_month"] = pd.to_datetime(curve["target_month"]) if "target_month" in curve.columns else pd.to_datetime(curve["Maturity"])
    forward_col = "expected_yoy_pct" if "expected_yoy_pct" in curve.columns else [c for c in curve.columns if "Expected Value" in c][0]

    rows: list[dict] = []
    for snap in snapshots:
        maturity = pd.Timestamp(snap.maturity)
        match = curve.loc[curve["target_month"] == maturity]
        if match.empty:
            # nearest match fallback
            idx = (curve["target_month"] - maturity).abs().idxmin()
            match = curve.loc[[idx]]
        parent_forward = float(match.iloc[0][forward_col])
        parent_std = float(match.iloc[0]["std_dev_pct"]) if "std_dev_pct" in match.columns else float(match.iloc[0].get("Std Dev (%)", np.nan))
        ttm = _ttm_years(maturity, valuation_date)

        sigmas = []
        anchor_threshold = None
        anchor_price = None
        if snap.binary_thresholds:
            for c in sorted(snap.binary_thresholds, key=lambda x: abs(x.threshold - parent_forward)):
                sigma = _binary_sigma_from_forward(parent_forward, c.threshold, c.price, ttm)
                if sigma is not None:
                    sigmas.append((sigma, c.threshold, c.price))
            if sigmas:
                ordered = sorted(sigmas, key=lambda x: abs(x[1] - parent_forward))
                anchor_threshold = ordered[0][1]
                anchor_price = ordered[0][2]

        if sigmas:
            implied_sigma = float(np.median([s[0] for s in sigmas]))
            source = "binary_inversion"
            n_obs = len(sigmas)
        else:
            implied_sigma = _pmf_sigma(snap) or (parent_std if math.isfinite(parent_std) and parent_std > 0 else np.nan)
            source = "pmf_proxy" if snap.exact_outcomes else "curve_std_fallback"
            n_obs = len(snap.exact_outcomes) if snap.exact_outcomes else 0
            if anchor_threshold is None:
                if snap.exact_outcomes:
                    anchor_threshold = min(snap.exact_outcomes, key=lambda x: abs(x.value - parent_forward)).value
                    anchor_price = min(snap.exact_outcomes, key=lambda x: abs(x.value - parent_forward)).price
                else:
                    anchor_threshold = parent_forward
                    anchor_price = 0.5

        if not math.isfinite(implied_sigma):
            implied_sigma = max(parent_std, 0.10)

        confidence = 100.0 * (
            0.45 * min(n_obs / 4.0, 1.0)
            + 0.35 * (1.0 if source == "binary_inversion" else 0.65)
            + 0.20 * min(max(ttm, 0.05) / 0.5, 1.0)
        )
        rows.append(
            {
                "target_month": maturity,
                "days_from_valuation": int(round(ttm * 365.25)),
                "parent_forward_pct": round(parent_forward, 4),
                "atm_threshold_pct": round(float(anchor_threshold), 4),
                "atm_contract_price": round(float(anchor_price), 4),
                "implied_vol_pct": round(float(implied_sigma), 4),
                "vol_source": source,
                "n_supporting_contracts": int(n_obs),
                "ttm_years": round(ttm, 4),
                "confidence_score": round(confidence, 1),
            }
        )

    return pd.DataFrame(rows).sort_values("days_from_valuation").reset_index(drop=True)


def build_forward_vol_scenarios(surface_df: pd.DataFrame, forward_shifts_bp: Iterable[float] = (-25, 0, 25), vol_multipliers: Iterable[float] = (0.8, 1.0, 1.2)) -> pd.DataFrame:
    rows: list[dict] = []
    for _, row in surface_df.iterrows():
        ttm = max(float(row["ttm_years"]), 1.0 / 365.25)
        base_forward = float(row["parent_forward_pct"])
        strike = float(row["atm_threshold_pct"])
        base_vol = max(float(row["implied_vol_pct"]), 0.01)
        for shift_bp in forward_shifts_bp:
            shifted_forward = base_forward + float(shift_bp) / 100.0
            for vm in vol_multipliers:
                sigma = max(base_vol * float(vm), 0.01)
                z = (shifted_forward - strike) / (sigma * math.sqrt(ttm))
                price = _NORMAL.cdf(z)
                rows.append(
                    {
                        "target_month": row["target_month"],
                        "days_from_valuation": row["days_from_valuation"],
                        "forward_shift_bp": float(shift_bp),
                        "vol_multiplier": float(vm),
                        "scenario_forward_pct": round(shifted_forward, 4),
                        "scenario_vol_pct": round(sigma, 4),
                        "scenario_event_price": round(float(price), 4),
                    }
                )
    return pd.DataFrame(rows)


def build_component_vol_framework(
    parent_surface: pd.DataFrame,
    component_specs: list[dict] | None = None,
) -> pd.DataFrame:
    specs = component_specs or [
        {"component": "Medical CPI", "beta_to_parent": 1.15, "correlation": 0.72},
        {"component": "Shelter CPI", "beta_to_parent": 0.95, "correlation": 0.88},
        {"component": "Core Services ex Shelter", "beta_to_parent": 1.05, "correlation": 0.81},
    ]
    rows: list[dict] = []
    for _, row in parent_surface.iterrows():
        parent_vol = max(float(row["implied_vol_pct"]), 0.01)
        for spec in specs:
            rho = min(max(float(spec["correlation"]), 0.15), 0.99)
            beta = max(float(spec["beta_to_parent"]), 0.10)
            comp_vol = parent_vol * beta / math.sqrt(rho)
            rows.append(
                {
                    "target_month": row["target_month"],
                    "days_from_valuation": row["days_from_valuation"],
                    "component": spec["component"],
                    "parent_implied_vol_pct": round(parent_vol, 4),
                    "beta_to_parent": round(beta, 3),
                    "correlation": round(rho, 3),
                    "component_implied_vol_pct": round(comp_vol, 4),
                }
            )
    return pd.DataFrame(rows)


def summarize_surface(surface_df: pd.DataFrame, diagnostics_df: pd.DataFrame | None = None) -> dict:
    summary = {
        "front_vol_pct": None,
        "back_vol_pct": None,
        "avg_vol_pct": None,
        "dispersion_avg_bp": None,
        "dispersion_peak_bp": None,
    }
    if not surface_df.empty:
        ordered = surface_df.sort_values("days_from_valuation")
        summary.update(
            {
                "front_vol_pct": round(float(ordered.iloc[0]["implied_vol_pct"]), 4),
                "back_vol_pct": round(float(ordered.iloc[-1]["implied_vol_pct"]), 4),
                "avg_vol_pct": round(float(ordered["implied_vol_pct"].mean()), 4),
            }
        )
    if diagnostics_df is not None and not diagnostics_df.empty and "abs_curve_diff_bp" in diagnostics_df.columns:
        summary.update(
            {
                "dispersion_avg_bp": round(float(diagnostics_df["abs_curve_diff_bp"].mean()), 2),
                "dispersion_peak_bp": round(float(diagnostics_df["abs_curve_diff_bp"].max()), 2),
            }
        )
    return summary


def build_vol_surface_artifacts(
    snapshots: Iterable[MaturitySnapshot],
    parent_curve: pd.DataFrame,
    valuation_date: pd.Timestamp,
    diagnostics_df: pd.DataFrame | None = None,
) -> VolSurfaceArtifacts:
    surface = build_binary_implied_vol_surface(snapshots, parent_curve, valuation_date)
    scenario_grid = build_forward_vol_scenarios(surface)
    component_surface = build_component_vol_framework(surface)
    summary = summarize_surface(surface, diagnostics_df)
    return VolSurfaceArtifacts(
        implied_vol=surface,
        scenario_grid=scenario_grid,
        component_surface=component_surface,
        summary=summary,
    )
