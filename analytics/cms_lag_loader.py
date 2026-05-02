"""
analytics/cms_lag_loader.py — Data loader for the CMS Lag Engine / Oriel Healthcare Reference tab.

Reads the 5 pipeline-generated artifacts from data/cms_lag_engine/.
The actual tab rendering lives in tabs/cms_tab.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd


def load_pipeline_outputs(output_dir: str | Path) -> Dict[str, pd.DataFrame | dict]:
    base = Path(output_dir)
    required = {
        "basis_action_panel": base / "basis_action_panel.csv",
        "cms_anchor_timeseries": base / "cms_anchor_timeseries.csv",
        "service_line_signal_panel": base / "service_line_signal_panel.csv",
        "historical_benchmark_panel": base / "historical_benchmark_panel.csv",
        "provenance_manifest": base / "provenance_manifest.json",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing CMS Lag Engine build artifacts: {missing}")
    loaded: Dict[str, pd.DataFrame | dict] = {}
    for name, path in required.items():
        if path.suffix == ".csv":
            loaded[name] = pd.read_csv(path)
        else:
            loaded[name] = json.loads(path.read_text())
    return loaded
