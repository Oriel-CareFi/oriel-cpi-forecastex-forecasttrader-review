from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.tier1_fv_engine import (
    apply_microstructure_filters,
    build_forecastex_curve_from_constituents,
    build_kalshi_curve_from_constituents,
    compute_enhanced_publishability,
    compute_governed_blend_weights,
    compute_venue_weight_diagnostics,
    compute_weight_calibration_summary,
    generate_trade_ideas,
    load_tier1_constituents,
    smooth_reference_curve,
    blend_curves,
    build_tier1_snapshot,
    build_venue_freshness_summary,
    build_blended_freshness_summary,
)

DATA_DIR = ROOT / "data"


def _prep():
    k = apply_microstructure_filters(load_tier1_constituents(DATA_DIR / "kalshi_constituents_current.csv"), "Kalshi")
    f = apply_microstructure_filters(load_tier1_constituents(DATA_DIR / "forecastex_constituents_current.csv"), "ForecastEx")
    kc = build_kalshi_curve_from_constituents(k)
    fc = build_forecastex_curve_from_constituents(f)
    kd = compute_venue_weight_diagnostics("Kalshi", 0.55, k, kc)
    fd = compute_venue_weight_diagnostics("ForecastEx", 0.45, f, fc)
    kw, fw = compute_governed_blend_weights(kd, fd)
    curve, meta = blend_curves(kc, fc, kw, fw, kd.eligible, fd.eligible)
    curve, smoothing = smooth_reference_curve(curve)
    return k, f, kc, fc, kd, fd, curve, meta, smoothing


def test_microstructure_filter_adds_required_columns():
    k, *_ = _prep()
    for col in ["proxy_spread_bp", "proxy_quote_age_seconds", "included_in_curve", "quote_selection_reason"]:
        assert col in k.columns
    assert k["included_in_curve"].isin([True, False]).all()


def test_smoothing_adds_diagnostics_columns():
    *_rest, curve, _meta, smoothing = _prep()
    assert "expected_yoy_raw_pct" in curve.columns
    assert "smoothing_residual_bp" in curve.columns
    assert smoothing.method_used in {"liquidity_weighted_monotone_linear", "nelson_siegel_proxy"}


def test_enhanced_publishability_returns_breakdown():
    k, f, kc, fc, kd, fd, curve, meta, _ = _prep()
    bf = build_blended_freshness_summary(
        build_venue_freshness_summary(k, "Kalshi"),
        build_venue_freshness_summary(f, "ForecastEx"),
    )
    pub, conf, score, breakdown = compute_enhanced_publishability(curve, meta, kd, fd, bf)
    assert pub in {"Eligible", "Review", "Draft"}
    assert conf in {"High", "Moderate", "Low"}
    assert 0 <= score <= 100
    assert "quality_score" in breakdown


def test_weight_calibration_summary_consistent():
    _k, _f, _kc, _fc, kd, fd, _curve, _meta, _ = _prep()
    summary = compute_weight_calibration_summary(kd, fd)
    assert summary["effective_weight_share_kalshi"] + summary["effective_weight_share_forecastex"] == 1.0


def test_trade_ideas_generated():
    _k, _f, _kc, _fc, kd, fd, curve, meta, _ = _prep()
    snap = build_tier1_snapshot(curve, 90, 10.0, meta)
    ideas = generate_trade_ideas(snap, curve, kd, fd)
    assert len(ideas) == 3
    assert all(idea.expression for idea in ideas)
