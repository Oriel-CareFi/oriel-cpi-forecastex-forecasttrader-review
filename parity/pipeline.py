from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

from .config import THRESHOLDS, ORIEL_CURVE_PATH, TIGHTER_BENCHMARK_PATH
from .curve_space import CurveGridSpec, build_curve_comparison_grid, compute_curve_shape_metrics
from .io_utils import load_oriel_curve, load_otc_quotes, load_dtcc_quotes
from .metrics import build_parity_table, summarize_parity


def run_parity(
    oriel_path: str | Path = ORIEL_CURVE_PATH,
    benchmark_path: str | Path = TIGHTER_BENCHMARK_PATH,
    is_dtcc: bool = False,
    output_dir: str | Path | None = None,
    curve_grid_freq: str = 'D',
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Run the OTC parity pipeline. Returns (parity_df, summary, grid_df)."""
    oriel_df  = load_oriel_curve(oriel_path)
    load_fn   = load_dtcc_quotes if is_dtcc else load_otc_quotes
    otc_df    = load_fn(benchmark_path)
    parity_df = build_parity_table(oriel_df, otc_df, tolerance_bps=THRESHOLDS.tolerance_bps)
    grid_df   = build_curve_comparison_grid(parity_df, spec=CurveGridSpec(freq=curve_grid_freq))
    shape_metrics = compute_curve_shape_metrics(parity_df, grid_df)
    summary   = summarize_parity(parity_df, thresholds=THRESHOLDS, shape_metrics=shape_metrics)

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        parity_df.to_csv(out / 'parity_output.csv', index=False)
        grid_df.to_csv(out / 'curve_grid_output.csv', index=False)
        with open(out / 'parity_summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        with open(out / 'shape_metrics.json', 'w', encoding='utf-8') as f:
            json.dump(shape_metrics, f, indent=2)

    return parity_df, summary, grid_df
