from __future__ import annotations
from dataclasses import asdict
import numpy as np
import pandas as pd

from .config import ThresholdConfig


def build_parity_table(oriel_df: pd.DataFrame, otc_df: pd.DataFrame, tolerance_bps: float) -> pd.DataFrame:
    merged = oriel_df.merge(otc_df, on="target_month", how="inner", validate="one_to_one")
    if merged.empty:
        raise ValueError("No overlapping target months between ORIEL and OTC benchmark files.")
    merged["otc_implied_index"] = merged["denominator_cpi"] * (1 + merged["otc_yoy_rate"] / 100.0)
    if "implied_future_index_level" in merged.columns:
        mask = merged["implied_future_index_level"].notna()
        merged.loc[mask, "otc_implied_index"] = merged.loc[mask, "implied_future_index_level"]
    merged["index_basis"] = merged["oriel_implied_index"] - merged["otc_implied_index"]
    merged["diff_bps"] = (merged["oriel_rate_pct"] - merged["otc_yoy_rate"]) * 100.0
    merged["abs_diff_bps"] = merged["diff_bps"].abs()
    merged["within_tolerance"] = merged["abs_diff_bps"] <= tolerance_bps
    merged["status"] = np.where(merged["within_tolerance"], "Pass", "Fail")
    return merged.sort_values("target_month").reset_index(drop=True)


def calculate_r2(oriel_rates: pd.Series, otc_rates: pd.Series) -> float:
    if len(oriel_rates) < 2:
        return float("nan")
    corr = np.corrcoef(oriel_rates, otc_rates)[0, 1]
    return float(corr ** 2)


def summarize_parity(parity_df: pd.DataFrame, thresholds: ThresholdConfig, shape_metrics: dict | None = None) -> dict:
    avg_abs = float(parity_df["abs_diff_bps"].mean())
    max_abs = float(parity_df["abs_diff_bps"].max())
    pct_within = float(parity_df["within_tolerance"].mean() * 100.0)
    r2 = calculate_r2(parity_df["oriel_rate_pct"], parity_df["otc_yoy_rate"])

    shape_metrics = shape_metrics or {}
    pillar_index_r2 = shape_metrics.get("pillar_r2_index")
    curve_index_r2  = shape_metrics.get("curve_r2_index")

    conditions = {
        "avg_abs_basis_within_limit":       avg_abs    <= thresholds.max_avg_abs_basis_bps,
        "max_abs_basis_within_limit":       max_abs    <= thresholds.max_max_abs_basis_bps,
        "pct_within_tolerance_sufficient":  pct_within >= thresholds.min_pct_within_tolerance,
        "pillar_index_r2_sufficient":       False if pillar_index_r2 is None else pillar_index_r2 >= thresholds.min_index_pillar_r2,
        "curve_index_r2_sufficient":        False if curve_index_r2 is None else curve_index_r2  >= thresholds.min_index_curve_r2,
    }
    basis_pass  = all(v for k, v in conditions.items() if not k.endswith("_r2_sufficient"))
    shape_pass  = conditions["pillar_index_r2_sufficient"] and conditions["curve_index_r2_sufficient"]
    overall_pass = basis_pass and shape_pass

    return {
        "months_tested":        int(len(parity_df)),
        "avg_abs_basis_bp":     round(avg_abs, 4),
        "max_abs_basis_bp":     round(max_abs, 4),
        "pct_within_tolerance": round(pct_within, 4),
        "tolerance_bps":        thresholds.tolerance_bps,
        "r_squared":            None if np.isnan(r2) else round(float(r2), 6),
        "shape_metrics":        shape_metrics,
        "conditions":           conditions,
        "basis_gate_status":    "PASS" if basis_pass  else "FAIL",
        "shape_gate_status":    "PASS" if shape_pass  else "FAIL",
        "overall_status":       "PASS" if overall_pass else "FAIL",
        "thresholds":           asdict(thresholds),
    }
