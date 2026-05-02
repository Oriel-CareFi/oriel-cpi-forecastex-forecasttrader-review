"""
dtcc_term_calibration.py — Loader for the DTCC CPI tenor-parity calibration handoff.

This module reads the by-tenor and monthly-by-tenor summary inputs from
data/dtcc_term_calibration/. It is **calibration / reference data**, not
parity fuel — there is no monthly target_month join, no PASS/FAIL gate,
and no Oriel comparison. The intent is to surface where the real OTC CPI
term structure is trading so it can be presented as an institutional
benchmark anchor next to the existing Oriel curve.

Schema is defined in data/dtcc_term_calibration/dtcc_cpi_tenor_parity_schema.json.
The full README ships in DTCC_CPI_TENOR_PARITY_HANDOFF_README.txt.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd

# Standard tenors typically shown in dashboards (per handoff README).
STANDARD_TENORS = ["1Y", "2Y", "3Y", "5Y", "10Y", "30Y"]


def load_term_calibration(base_dir: str | Path) -> Dict[str, pd.DataFrame | dict]:
    """Load every artifact in the tenor calibration handoff.

    Returns a dict with:
        by_tenor       — by-tenor summary (one row per tenor)
        monthly        — execution-month × tenor summary
        trade_level    — normalized trade-level rows
        oriel_template — empty Oriel term-rate template (placeholder for future joins)
        schema         — schema JSON
    """
    base = Path(base_dir)
    required = {
        "by_tenor":       base / "dtcc_cpi_tenor_parity_summary_input.csv",
        "monthly":        base / "dtcc_cpi_tenor_parity_monthly_summary_input.csv",
        "trade_level":    base / "dtcc_cpi_tenor_parity_trade_input.csv",
        "oriel_template": base / "oriel_term_parity_template.csv",
        "schema":         base / "dtcc_cpi_tenor_parity_schema.json",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing DTCC term calibration artifacts: {missing}")

    loaded: Dict[str, pd.DataFrame | dict] = {}
    for name, path in required.items():
        if path.suffix == ".csv":
            loaded[name] = pd.read_csv(path)
        else:
            loaded[name] = json.loads(path.read_text())
    return loaded


def filter_standard_tenors(by_tenor_df: pd.DataFrame) -> pd.DataFrame:
    """Subset the by-tenor summary to the six standard institutional tenors."""
    if by_tenor_df is None or by_tenor_df.empty:
        return by_tenor_df
    df = by_tenor_df.copy()
    df = df[df["target_tenor_label"].isin(STANDARD_TENORS)].copy()
    # Sort by tenor in months so curve plots ascend left → right
    df = df.sort_values("target_tenor_months").reset_index(drop=True)
    return df
