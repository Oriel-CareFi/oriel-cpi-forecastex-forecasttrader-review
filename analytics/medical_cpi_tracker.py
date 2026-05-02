from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
DEFAULT_BREADTH_THRESHOLD = 3.0

# Unadjusted CPI-U U.S. city average series IDs keep the panel internally consistent,
# including health insurance, which is only published unadjusted at the U.S. level.
SERIES_CONFIG: Dict[str, Dict[str, object]] = {
    "Medical care": {"series_id": "CUUR0000SAM", "weight": 8.431, "group": "aggregate"},
    "Medical care services": {"series_id": "CUUR0000SAM2", "weight": 6.956, "group": "breadth"},
    "Medical care commodities": {"series_id": "CUUR0000SAM1", "weight": 1.475, "group": "breadth"},
    "Physicians' services": {"series_id": "CUUR0000SEMC01", "weight": 1.680, "group": "breadth"},
    "Hospital services": {"series_id": "CUUR0000SEMD01", "weight": 2.183, "group": "breadth"},
    "Prescription drugs": {"series_id": "CUUR0000SEMF01", "weight": 0.963, "group": "breadth"},
    "Health insurance": {"series_id": "CUUR0000SEME", "weight": 0.864, "group": "breadth"},
}

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "medical_cpi_tracker"
SEED_PATH = SEED_DIR / "medical_cpi_seed.csv"


@dataclass(frozen=True)
class MedicalCPIPanel:
    latest_table: pd.DataFrame
    history: pd.DataFrame
    breadth: Dict[str, float | str | int | None]
    source_status: str
    source_detail: str
    as_of_label: str


@dataclass(frozen=True)
class MedicalCPISeriesPoint:
    component: str
    series_id: str
    date: pd.Timestamp
    level: float


def _month_label(ts: pd.Timestamp) -> str:
    return ts.strftime("%b %Y")


def _years_window(now: Optional[pd.Timestamp] = None, years_back: int = 3) -> Tuple[str, str]:
    now = now or pd.Timestamp.utcnow().tz_localize(None)
    return str(int(now.year) - years_back), str(int(now.year))


def fetch_bls_medical_cpi_history(timeout_seconds: float = 20.0) -> pd.DataFrame:
    startyear, endyear = _years_window()
    payload = {
        "seriesid": [cfg["series_id"] for cfg in SERIES_CONFIG.values()],
        "startyear": startyear,
        "endyear": endyear,
        "registrationkey": "",
    }
    response = requests.post(BLS_API_URL, json=payload, timeout=timeout_seconds)
    response.raise_for_status()
    raw = response.json()
    if raw.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS request failed: {json.dumps(raw)[:300]}")

    rows: List[dict] = []
    label_by_series = {cfg["series_id"]: label for label, cfg in SERIES_CONFIG.items()}
    weight_by_label = {label: float(cfg["weight"]) for label, cfg in SERIES_CONFIG.items()}
    group_by_label = {label: str(cfg["group"]) for label, cfg in SERIES_CONFIG.items()}

    for series in raw.get("Results", {}).get("series", []):
        series_id = series.get("seriesID") or series.get("seriesId")
        component = label_by_series.get(series_id)
        if not component:
            continue
        for obs in series.get("data", []):
            period = obs.get("period")
            if not isinstance(period, str) or not period.startswith("M") or period == "M13":
                continue
            try:
                month = int(period[1:])
                year = int(obs["year"])
                value = float(obs["value"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append({
                "component": component,
                "series_id": series_id,
                "date": pd.Timestamp(year=year, month=month, day=1),
                "level": value,
                "weight": weight_by_label[component],
                "group": group_by_label[component],
            })

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("BLS returned no medical CPI observations.")
    return df.sort_values(["component", "date"]).reset_index(drop=True)


def load_seed_medical_cpi_history(seed_path: Path | str = SEED_PATH) -> pd.DataFrame:
    seed_path = Path(seed_path)
    df = pd.read_csv(seed_path, parse_dates=["date"])
    return df.sort_values(["component", "date"]).reset_index(drop=True)


def _compute_component_metrics(history: pd.DataFrame) -> pd.DataFrame:
    pieces: List[pd.DataFrame] = []
    for component, grp in history.groupby("component", sort=False):
        g = grp.sort_values("date").copy()
        g["mom_pct"] = (g["level"] / g["level"].shift(1) - 1.0) * 100.0
        g["yoy_pct"] = (g["level"] / g["level"].shift(12) - 1.0) * 100.0
        g["prev_yoy_pct"] = g["yoy_pct"].shift(1)
        pieces.append(g)
    out = pd.concat(pieces, ignore_index=True)
    return out.sort_values(["component", "date"]).reset_index(drop=True)


def _latest_table(history: pd.DataFrame) -> pd.DataFrame:
    metric_df = _compute_component_metrics(history)
    latest_rows = (
        metric_df.sort_values(["component", "date"]) 
        .groupby("component", as_index=False)
        .tail(1)
        .copy()
    )
    latest_rows["component_order"] = latest_rows["component"].map({name: i for i, name in enumerate(SERIES_CONFIG.keys())})
    latest_rows = latest_rows.sort_values("component_order").drop(columns=["component_order"])
    latest_rows.rename(columns={
        "mom_pct": "M/M (%)",
        "yoy_pct": "Y/Y (%)",
        "prev_yoy_pct": "Prev Y/Y",
        "level": "Index Level",
        "date": "As Of",
        "weight": "Weight",
    }, inplace=True)
    return latest_rows.reset_index(drop=True)


def _compute_breadth(latest_table: pd.DataFrame, threshold_pct: float = DEFAULT_BREADTH_THRESHOLD) -> Dict[str, float | str | int | None]:
    breadth_df = latest_table[latest_table["group"] == "breadth"].copy()
    breadth_df = breadth_df.dropna(subset=["Y/Y (%)", "Prev Y/Y", "Weight"])
    if breadth_df.empty:
        return {
            "accelerating_share": None,
            "weighted_share_above_threshold": None,
            "dispersion_std": None,
            "threshold_pct": threshold_pct,
            "component_count": 0,
        }

    weights = breadth_df["Weight"].astype(float)
    weight_total = float(weights.sum()) or 1.0
    accelerating = (breadth_df["Y/Y (%)"] > breadth_df["Prev Y/Y"]).astype(float)
    above_threshold = (breadth_df["Y/Y (%)"] >= threshold_pct).astype(float)

    return {
        "accelerating_share": float(accelerating.mean() * 100.0),
        "weighted_share_above_threshold": float(((above_threshold * weights).sum() / weight_total) * 100.0),
        "dispersion_std": float(breadth_df["Y/Y (%)"].astype(float).std(ddof=0)),
        "threshold_pct": float(threshold_pct),
        "component_count": int(len(breadth_df)),
    }


def load_medical_cpi_panel(prefer_live: bool = True, seed_path: Path | str = SEED_PATH) -> MedicalCPIPanel:
    source_status = "seed"
    source_detail = f"Fallback seed file: {Path(seed_path).name}"
    try:
        history = fetch_bls_medical_cpi_history() if prefer_live else load_seed_medical_cpi_history(seed_path)
        source_status = "live" if prefer_live else "seed"
        source_detail = "Live BLS API" if prefer_live else source_detail
    except Exception as exc:
        history = load_seed_medical_cpi_history(seed_path)
        source_status = "fallback"
        source_detail = f"Live BLS unavailable; using seed file ({type(exc).__name__})"

    latest = _latest_table(history)
    breadth = _compute_breadth(latest)
    as_of = pd.to_datetime(latest["As Of"].max()) if not latest.empty else pd.NaT
    as_of_label = _month_label(as_of) if pd.notna(as_of) else "—"
    return MedicalCPIPanel(
        latest_table=latest,
        history=history,
        breadth=breadth,
        source_status=source_status,
        source_detail=source_detail,
        as_of_label=as_of_label,
    )
