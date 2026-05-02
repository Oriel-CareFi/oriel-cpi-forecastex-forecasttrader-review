from __future__ import annotations
from pathlib import Path
import pandas as pd


def load_oriel_curve(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path).copy()
    required = {"target_month", "denominator_cpi", "oriel_implied_index", "oriel_rate_pct"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"ORIEL curve file missing required columns: {sorted(missing)}")
    df["target_month"] = pd.to_datetime(df["target_month"]).dt.normalize()
    for col in ["denominator_cpi", "oriel_implied_index", "oriel_rate_pct"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    df["oriel_rate_decimal"] = df["oriel_rate_pct"] / 100.0
    return df.sort_values("target_month").reset_index(drop=True)


def load_otc_quotes(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path).copy()
    required = {"target_month", "otc_yoy_rate"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OTC benchmark file missing required columns: {sorted(missing)}")
    df["target_month"] = pd.to_datetime(df["target_month"]).dt.normalize()
    df["otc_yoy_rate"] = pd.to_numeric(df["otc_yoy_rate"], errors="raise")
    optional_numeric = ["known_base_index", "implied_future_index_level"]
    for col in optional_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    agg_map: dict = {"otc_yoy_rate": "median"}
    for col in ["quote_date", "otc_quote_type", "source", "quality_flag", "notes",
                "known_base_index", "implied_future_index_level"]:
        if col in df.columns:
            agg_map[col] = "first"
    grouped = df.groupby("target_month", as_index=False).agg(agg_map)
    grouped["otc_rate_decimal"] = grouped["otc_yoy_rate"] / 100.0
    return grouped.sort_values("target_month").reset_index(drop=True)


def load_dtcc_quotes(path: str | Path) -> pd.DataFrame:
    """Load a DTCC SDR-format file. Renames fixed_rate -> otc_yoy_rate and
    aggregates multiple prints per target_month to median, producing the same
    column contract as load_otc_quotes()."""
    df = pd.read_csv(path).copy()
    required = {"target_month", "fixed_rate"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DTCC file missing required columns: {sorted(missing)}")
    df = df.rename(columns={"fixed_rate": "otc_yoy_rate"})
    df["target_month"] = pd.to_datetime(df["target_month"]).dt.normalize()
    df["otc_yoy_rate"] = pd.to_numeric(df["otc_yoy_rate"], errors="raise")
    optional_numeric = ["known_base_index", "implied_future_index_level"]
    for col in optional_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    agg_map: dict = {"otc_yoy_rate": "median"}
    for col in ["quote_date", "source", "quality_flag", "notes",
                "known_base_index", "implied_future_index_level"]:
        if col in df.columns:
            agg_map[col] = "first"
    grouped = df.groupby("target_month", as_index=False).agg(agg_map)
    grouped["otc_rate_decimal"] = grouped["otc_yoy_rate"] / 100.0
    return grouped.sort_values("target_month").reset_index(drop=True)
