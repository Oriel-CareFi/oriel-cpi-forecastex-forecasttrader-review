from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd

GridFrequency = Literal['D', 'W', 'MS']


@dataclass(frozen=True)
class CurveGridSpec:
    freq: GridFrequency = 'D'


def _date_to_ordinal(values: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    dt = pd.to_datetime(values)
    return dt.astype('int64').astype(float) / 86_400_000_000_000.0


def build_common_grid(start_date: pd.Timestamp, end_date: pd.Timestamp, spec: CurveGridSpec | None = None) -> pd.DatetimeIndex:
    spec = spec or CurveGridSpec()
    return pd.date_range(start=start_date, end=end_date, freq=spec.freq)


def interpolate_index_curve(df: pd.DataFrame, index_col: str, grid: pd.DatetimeIndex, floor_value: float = 1e-9) -> pd.DataFrame:
    if df.empty:
        raise ValueError('Cannot interpolate an empty curve.')
    work = df.sort_values('target_month').copy()
    x = _date_to_ordinal(work['target_month'])
    y = np.log(np.maximum(work[index_col].astype(float).to_numpy(), floor_value))
    xg = _date_to_ordinal(grid)
    yg = np.interp(xg, x, y)
    return pd.DataFrame({'target_month': grid, index_col: np.exp(yg)})


def build_curve_comparison_grid(parity_df: pd.DataFrame, spec: CurveGridSpec | None = None) -> pd.DataFrame:
    spec = spec or CurveGridSpec()
    start = pd.to_datetime(parity_df['target_month']).min()
    end   = pd.to_datetime(parity_df['target_month']).max()
    grid  = build_common_grid(start, end, spec=spec)

    oriel = parity_df[['target_month', 'oriel_implied_index']].drop_duplicates()
    otc   = parity_df[['target_month', 'otc_implied_index']].drop_duplicates()
    oriel_grid = interpolate_index_curve(oriel, 'oriel_implied_index', grid)
    otc_grid   = interpolate_index_curve(otc,   'otc_implied_index',   grid)
    merged = oriel_grid.merge(otc_grid, on='target_month', how='inner', validate='one_to_one')
    merged['index_basis'] = merged['oriel_implied_index'] - merged['otc_implied_index']
    return merged.sort_values('target_month').reset_index(drop=True)


def compute_curve_shape_metrics(observed_df: pd.DataFrame, grid_df: pd.DataFrame) -> dict:
    def _safe_r2(a: pd.Series, b: pd.Series) -> float | None:
        if len(a) < 2:
            return None
        corr = np.corrcoef(a.astype(float), b.astype(float))[0, 1]
        if np.isnan(corr):
            return None
        return float(corr ** 2)

    pillar_r2_index = _safe_r2(observed_df['oriel_implied_index'], observed_df['otc_implied_index'])
    curve_r2_index  = _safe_r2(grid_df['oriel_implied_index'],     grid_df['otc_implied_index'])
    pillar_r2_rate  = _safe_r2(observed_df['oriel_rate_pct'],       observed_df['otc_yoy_rate'])

    index_rmse    = float(np.sqrt(np.mean((observed_df['oriel_implied_index'] - observed_df['otc_implied_index']) ** 2)))
    rate_rmse_bps = float(np.sqrt(np.mean((observed_df['oriel_rate_pct']      - observed_df['otc_yoy_rate']) ** 2)) * 100.0)

    return {
        'pillar_r2_index':  None if pillar_r2_index is None else round(pillar_r2_index, 6),
        'curve_r2_index':   None if curve_r2_index  is None else round(curve_r2_index,  6),
        'pillar_r2_rate':   None if pillar_r2_rate  is None else round(pillar_r2_rate,  6),
        'index_rmse':       round(index_rmse,    6),
        'rate_rmse_bps':    round(rate_rmse_bps, 6),
        'curve_grid_points': int(len(grid_df)),
    }
