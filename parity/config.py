from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

ROOT       = Path(__file__).resolve().parent.parent  # project root, not parity/
DATA_DIR   = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"

ORIEL_CURVE_PATH        = DATA_DIR / "oriel_curve_sample.csv"
TIGHTER_BENCHMARK_PATH  = DATA_DIR / "otc_cpi_quotes_tighter_demo.csv"
DTCC_BENCHMARK_PATH     = DATA_DIR / "dtcc_cpi_static_demo_2026Q2.csv"
NEGATIVE_CONTROL_PATH   = DATA_DIR / "otc_cpi_quotes_negative_control.csv"


@dataclass(frozen=True)
class ThresholdConfig:
    tolerance_bps: float             = 10.0
    max_avg_abs_basis_bps: float     = 10.0
    max_max_abs_basis_bps: float     = 10.0
    min_pct_within_tolerance: float  = 100.0
    min_index_curve_r2: float        = 0.95
    min_index_pillar_r2: float       = 0.95


THRESHOLDS = ThresholdConfig()
