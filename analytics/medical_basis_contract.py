"""
analytics/medical_basis_contract.py — Medical inflation vs. CPI basis contract engine.

Purpose
-------
Turns an illustrative ForecastEx-style YES/NO spread-contract ladder into:
  • explicit CPI-U and Medical CPI YoY reference legs
  • threshold-ladder probabilities: P(Medical CPI YoY - CPI-U YoY > threshold)
  • an implied spread distribution
  • expected medical-vs-CPI basis by maturity
  • settlement calculations for objective BLS prints

The module is intentionally self-contained and data-frame friendly so it can be
used by Streamlit tabs, tests, notebooks, and future venue adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import math
import pandas as pd


DEFAULT_THRESHOLDS_BPS: tuple[int, ...] = (0, 100, 200, 300, 400)
DEFAULT_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "medical_basis_sample_contracts.csv"


@dataclass(frozen=True)
class ReferenceLeg:
    """Reference leg used in the medical-vs-CPI basis contract."""

    name: str
    description: str
    source: str
    calculation: str


@dataclass(frozen=True)
class MedicalBasisContractSpec:
    """Human-readable contract specification."""

    contract_name: str = "ForecastEx: Medical Inflation Basis Contract"
    question: str = (
        "Will U.S. medical inflation exceed U.S. headline CPI inflation by more "
        "than the stated spread threshold for the observation window?"
    )
    reference_leg_1: ReferenceLeg = ReferenceLeg(
        name="BLS CPI-U YoY",
        description="Headline U.S. CPI-U year-over-year inflation.",
        source="Bureau of Labor Statistics CPI-U",
        calculation="Annual average YoY or December-over-December YoY, as specified by contract terms.",
    )
    reference_leg_2: ReferenceLeg = ReferenceLeg(
        name="BLS Medical Care CPI YoY",
        description="Medical care CPI year-over-year inflation.",
        source="Bureau of Labor Statistics Medical Care CPI",
        calculation="Annual average YoY or December-over-December YoY, as specified by contract terms.",
    )
    payout: str = "$1.00 if Medical CPI YoY - CPI-U YoY exceeds threshold; otherwise $0.00"
    starting_thresholds_bps: tuple[int, ...] = DEFAULT_THRESHOLDS_BPS
    observation_window: str = "Calendar year 2027 / official year-end print"
    users: str = "Providers, payers, employers, reinsurers, macro traders"
    phase_label: str = "Illustrative ForecastEx-style contract design"


@dataclass(frozen=True)
class SettlementResult:
    """Settlement result for a single threshold contract."""

    cpi_yoy_pct: float
    medical_cpi_yoy_pct: float
    spread_pct: float
    spread_bps: float
    threshold_bps: int
    settles_yes: bool
    payout: float


@dataclass(frozen=True)
class BasisCurvePoint:
    """Expected medical-vs-CPI basis for a maturity."""

    maturity: pd.Timestamp
    observation_window: str
    expected_spread_bps: float
    expected_spread_pct: float
    probability_spread_gt_0: float
    probability_spread_gt_200: float
    max_threshold_bps: int
    source_status: str


@dataclass(frozen=True)
class BasisCurve:
    """Container for basis-curve outputs and intermediate tables."""

    points: list[BasisCurvePoint]
    ladder: pd.DataFrame
    distribution: pd.DataFrame
    repaired: bool
    source_status: str


def contract_spec_dataframe(spec: MedicalBasisContractSpec | None = None) -> pd.DataFrame:
    """Return contract-spec rows suitable for a UI table."""
    spec = spec or MedicalBasisContractSpec()
    rows = [
        ("Question", spec.question),
        ("Reference leg 1", spec.reference_leg_1.name),
        ("Reference leg 2", spec.reference_leg_2.name),
        ("Settlement", spec.payout),
        ("Users", spec.users),
        ("Observation window", spec.observation_window),
        ("Status", spec.phase_label),
    ]
    return pd.DataFrame(rows, columns=["Field", "Value"])


def load_sample_medical_basis_contracts(path: str | Path | None = None) -> pd.DataFrame:
    """Load the sample medical-basis ladder CSV.

    The sample represents illustrative YES prices for contracts of the form:
    P(Medical CPI YoY - CPI-U YoY > threshold_bps).
    """
    csv_path = Path(path) if path is not None else DEFAULT_SAMPLE_PATH
    df = pd.read_csv(csv_path)
    return normalize_ladder_frame(df)


def normalize_ladder_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a ladder frame."""
    required = {"maturity", "threshold_bps", "yes_price"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"medical basis ladder is missing required columns: {sorted(missing)}")

    out = df.copy()
    out["maturity"] = pd.to_datetime(out["maturity"])
    out["threshold_bps"] = out["threshold_bps"].astype(int)
    out["yes_price"] = out["yes_price"].astype(float).clip(0.0, 1.0)

    if "observation_window" not in out.columns:
        out["observation_window"] = out["maturity"].dt.strftime("%Y")
    if "source" not in out.columns:
        out["source"] = "sample"
    if "source_status" not in out.columns:
        out["source_status"] = "SAMPLE"
    if "contract_label" not in out.columns:
        out["contract_label"] = out["threshold_bps"].map(lambda x: f"Spread > {x} bps")

    return out.sort_values(["maturity", "threshold_bps"]).reset_index(drop=True)


def repair_exceedance_ladder(yes_prices: Sequence[float]) -> tuple[list[float], bool]:
    """Enforce non-increasing exceedance probabilities.

    For a threshold ladder, P(spread > 300) cannot exceed P(spread > 200).
    This simple monotonic repair is deterministic and avoids an optional scipy
    dependency. It preserves probabilities when already valid.
    """
    repaired: list[float] = []
    changed = False
    last = 1.0
    for raw in yes_prices:
        p = min(max(float(raw), 0.0), 1.0)
        if p > last:
            p = last
            changed = True
        repaired.append(p)
        last = p
    return repaired, changed


def ladder_to_distribution(
    thresholds_bps: Sequence[int],
    yes_prices: Sequence[float],
    *,
    maturity: pd.Timestamp | str | None = None,
    observation_window: str | None = None,
) -> tuple[pd.DataFrame, bool]:
    """Convert exceedance probabilities into bucket probabilities.

    If yes_prices are [P(>0), P(>100), ...], then bucket probabilities are:
      P(<=0)      = 1 - P(>0)
      P(0,100]   = P(>0) - P(>100)
      ...
      P(>400)    = P(>400)
    """
    if len(thresholds_bps) != len(yes_prices):
        raise ValueError("thresholds_bps and yes_prices must have equal length")
    if len(thresholds_bps) == 0:
        raise ValueError("threshold ladder cannot be empty")

    thresholds = [int(x) for x in thresholds_bps]
    if thresholds != sorted(thresholds):
        raise ValueError("thresholds_bps must be ascending")

    prices, changed = repair_exceedance_ladder(yes_prices)
    step = min([b - a for a, b in zip(thresholds[:-1], thresholds[1:])] or [100])

    rows: list[dict] = []
    # <= first threshold bucket
    rows.append({
        "bucket": f"≤ {thresholds[0]} bps",
        "lower_bps": float("-inf"),
        "upper_bps": thresholds[0],
        "midpoint_bps": thresholds[0] - step / 2,
        "probability": max(0.0, 1.0 - prices[0]),
        "maturity": pd.to_datetime(maturity) if maturity is not None else pd.NaT,
        "observation_window": observation_window or "",
    })
    for i in range(len(thresholds) - 1):
        lo = thresholds[i]
        hi = thresholds[i + 1]
        rows.append({
            "bucket": f"> {lo} to ≤ {hi} bps",
            "lower_bps": lo,
            "upper_bps": hi,
            "midpoint_bps": (lo + hi) / 2,
            "probability": max(0.0, prices[i] - prices[i + 1]),
            "maturity": pd.to_datetime(maturity) if maturity is not None else pd.NaT,
            "observation_window": observation_window or "",
        })
    rows.append({
        "bucket": f"> {thresholds[-1]} bps",
        "lower_bps": thresholds[-1],
        "upper_bps": float("inf"),
        "midpoint_bps": thresholds[-1] + step / 2,
        "probability": max(0.0, prices[-1]),
        "maturity": pd.to_datetime(maturity) if maturity is not None else pd.NaT,
        "observation_window": observation_window or "",
    })
    dist = pd.DataFrame(rows)
    total = float(dist["probability"].sum())
    if total > 0 and not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        dist["probability"] = dist["probability"] / total
        changed = True
    return dist, changed


def expected_spread_bps(distribution: pd.DataFrame) -> float:
    """Expected spread in bps from bucket distribution midpoints."""
    if distribution.empty:
        return float("nan")
    return float((distribution["midpoint_bps"].astype(float) * distribution["probability"].astype(float)).sum())


def build_basis_curve(ladder_df: pd.DataFrame) -> BasisCurve:
    """Build expected medical-vs-CPI basis by maturity from ladder prices."""
    df = normalize_ladder_frame(ladder_df)
    dist_frames: list[pd.DataFrame] = []
    points: list[BasisCurvePoint] = []
    repaired_any = False

    for maturity, group in df.groupby("maturity", sort=True):
        g = group.sort_values("threshold_bps")
        observation_window = str(g["observation_window"].iloc[0])
        dist, repaired = ladder_to_distribution(
            list(g["threshold_bps"]),
            list(g["yes_price"]),
            maturity=maturity,
            observation_window=observation_window,
        )
        repaired_any = repaired_any or repaired
        dist_frames.append(dist)
        exp_bps = expected_spread_bps(dist)
        p_gt_0 = float(g.loc[g["threshold_bps"] == 0, "yes_price"].iloc[0]) if (g["threshold_bps"] == 0).any() else float("nan")
        p_gt_200 = float(g.loc[g["threshold_bps"] == 200, "yes_price"].iloc[0]) if (g["threshold_bps"] == 200).any() else float("nan")
        source_status = str(g.get("source_status", pd.Series(["SAMPLE"])).iloc[0])
        points.append(BasisCurvePoint(
            maturity=pd.to_datetime(maturity),
            observation_window=observation_window,
            expected_spread_bps=exp_bps,
            expected_spread_pct=exp_bps / 100.0,
            probability_spread_gt_0=p_gt_0,
            probability_spread_gt_200=p_gt_200,
            max_threshold_bps=int(g["threshold_bps"].max()),
            source_status=source_status,
        ))

    distribution = pd.concat(dist_frames, ignore_index=True) if dist_frames else pd.DataFrame()
    source_status = "SAMPLE" if not df.empty and str(df["source_status"].iloc[0]).upper() == "SAMPLE" else "LIVE_OR_CUSTOM"
    return BasisCurve(points=points, ladder=df, distribution=distribution, repaired=repaired_any, source_status=source_status)


def basis_curve_dataframe(curve: BasisCurve) -> pd.DataFrame:
    """Convert BasisCurve points into a DataFrame for charts/tables."""
    return pd.DataFrame([p.__dict__ for p in curve.points])


def settle_medical_basis_contract(
    *,
    cpi_yoy_pct: float,
    medical_cpi_yoy_pct: float,
    threshold_bps: int = 200,
    payout_yes: float = 1.0,
    payout_no: float = 0.0,
) -> SettlementResult:
    """Calculate objective binary settlement from realized reference prints."""
    spread_pct = float(medical_cpi_yoy_pct) - float(cpi_yoy_pct)
    spread_bps = spread_pct * 100.0
    settles_yes = spread_bps > float(threshold_bps)
    payout = float(payout_yes if settles_yes else payout_no)
    return SettlementResult(
        cpi_yoy_pct=float(cpi_yoy_pct),
        medical_cpi_yoy_pct=float(medical_cpi_yoy_pct),
        spread_pct=spread_pct,
        spread_bps=spread_bps,
        threshold_bps=int(threshold_bps),
        settles_yes=settles_yes,
        payout=payout,
    )


def settlement_example() -> SettlementResult:
    """Slide-aligned example: Medical CPI 5.6%, CPI 3.1%, 250 bps spread, settles YES."""
    return settle_medical_basis_contract(cpi_yoy_pct=3.1, medical_cpi_yoy_pct=5.6, threshold_bps=200)
