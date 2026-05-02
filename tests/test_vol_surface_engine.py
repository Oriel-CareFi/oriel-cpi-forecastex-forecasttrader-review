from pathlib import Path
import pandas as pd

from analytics.tier1_fv_engine import (
    apply_microstructure_filters,
    build_forecastex_curve_from_constituents,
    build_kalshi_curve_from_constituents,
    blend_curves,
    compute_governed_blend_weights,
    compute_venue_weight_diagnostics,
    load_tier1_constituents,
    smooth_reference_curve,
)
from analytics.vol_surface_engine import build_vol_surface_artifacts
from sample_data import CPI_SNAPSHOTS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_vol_surface_artifacts():
    data_dir = PROJECT_ROOT / 'data'
    kalshi = apply_microstructure_filters(load_tier1_constituents(data_dir / 'kalshi_constituents_current.csv'), 'Kalshi')
    forecastex = apply_microstructure_filters(load_tier1_constituents(data_dir / 'forecastex_constituents_current.csv'), 'ForecastEx')
    kc = build_kalshi_curve_from_constituents(kalshi)
    fc = build_forecastex_curve_from_constituents(forecastex)
    kd = compute_venue_weight_diagnostics('Kalshi', 0.55, kalshi, kc)
    fd = compute_venue_weight_diagnostics('ForecastEx', 0.45, forecastex, fc)
    kw, fw = compute_governed_blend_weights(kd, fd)
    blended, _ = blend_curves(kc, fc, kw, fw, kd.eligible, fd.eligible)
    blended, _ = smooth_reference_curve(blended, pd.concat([kalshi, forecastex], ignore_index=True))

    artifacts = build_vol_surface_artifacts(CPI_SNAPSHOTS, blended, pd.Timestamp('2026-01-01'))
    assert not artifacts.implied_vol.empty
    assert {'implied_vol_pct', 'parent_forward_pct', 'vol_source'}.issubset(artifacts.implied_vol.columns)
    assert artifacts.implied_vol['implied_vol_pct'].gt(0).all()
    assert not artifacts.scenario_grid.empty
    assert not artifacts.component_surface.empty
