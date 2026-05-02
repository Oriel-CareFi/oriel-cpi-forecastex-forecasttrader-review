from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.brier_calibration import load_calibration_history, compute_calibration_summary
from analytics.tier1_fv_engine import (
    load_tier1_constituents,
    build_kalshi_curve_from_constituents,
    build_forecastex_curve_from_constituents,
    compute_venue_weight_diagnostics,
    compute_weight_calibration_summary,
    compute_governed_blend_weights,
)

DATA_DIR = ROOT / 'data'


def test_calibration_history_loads():
    hist = load_calibration_history()
    assert not hist.empty
    assert {'venue', 'contract_family', 'horizon_bucket', 'mean_brier_score'}.issubset(hist.columns)


def test_venue_calibration_summary_populates_scores():
    hist = load_calibration_history()
    k = load_tier1_constituents(DATA_DIR / 'kalshi_constituents_current.csv')
    summary = compute_calibration_summary(hist, 'Kalshi', k)
    assert 0 <= summary.historical_calibration_score <= 100
    assert 0 <= summary.brier_skill_score <= 100
    assert summary.calibration_sample_size > 0
    assert summary.weighted_mean_brier_score < 0.25


def test_venue_weight_diag_includes_calibration_fields():
    hist = load_calibration_history()
    k = load_tier1_constituents(DATA_DIR / 'kalshi_constituents_current.csv')
    kc = build_kalshi_curve_from_constituents(k)
    kd = compute_venue_weight_diagnostics('Kalshi', 0.55, k, kc, hist)
    assert kd.historical_calibration_score > 0
    assert kd.weighted_mean_brier_score < 0.25
    assert kd.calibration_sample_size > 0
    assert kd.contract_family_calibration is not None


def test_weight_calibration_summary_includes_brier_fields():
    hist = load_calibration_history()
    k = load_tier1_constituents(DATA_DIR / 'kalshi_constituents_current.csv')
    f = load_tier1_constituents(DATA_DIR / 'forecastex_constituents_current.csv')
    kc = build_kalshi_curve_from_constituents(k)
    fc = build_forecastex_curve_from_constituents(f)
    kd = compute_venue_weight_diagnostics('Kalshi', 0.55, k, kc, hist)
    fd = compute_venue_weight_diagnostics('ForecastEx', 0.45, f, fc, hist)
    compute_governed_blend_weights(kd, fd)
    summary = compute_weight_calibration_summary(kd, fd)
    assert 'kalshi_historical_calibration_score' in summary
    assert 'forecastex_weighted_mean_brier_score' in summary
    assert summary['effective_weight_share_kalshi'] + summary['effective_weight_share_forecastex'] == 1.0
