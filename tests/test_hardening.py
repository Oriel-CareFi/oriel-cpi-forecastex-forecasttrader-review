"""Tests for the hardening package: distribution, weighting, freshness."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from analytics.tier1_fv_engine import (
    VenueCurvePoint, BlendedReferencePoint, VenueWeightDiagnostics,
    VenueFreshnessSummary, BlendedFreshnessSummary,
    load_tier1_constituents, build_kalshi_curve_from_constituents,
    build_forecastex_curve_from_constituents, blend_curves,
    compute_distribution_metrics, compute_blended_reference_points,
    compute_venue_weight_diagnostics, compute_governed_blend_weights,
    build_venue_freshness_summary, build_blended_freshness_summary,
    generate_freshness_commentary, compute_raw_venue_score,
    score_venue_liquidity, score_venue_coverage, score_venue_consistency,
    BLEND_ALPHA,
)


DATA_DIR = ROOT / "data"


def _load_test_data():
    k = load_tier1_constituents(DATA_DIR / "kalshi_constituents_current.csv")
    f = load_tier1_constituents(DATA_DIR / "forecastex_constituents_current.csv")
    kc = build_kalshi_curve_from_constituents(k)
    fc = build_forecastex_curve_from_constituents(f)
    return k, f, kc, fc


def test_distribution_metrics_returns_correct_count():
    k, f, kc, fc = _load_test_data()
    pts = compute_distribution_metrics(kc, k)
    assert len(pts) == len(kc), f"Expected {len(kc)} distribution points, got {len(pts)}"
    assert all(isinstance(p, VenueCurvePoint) for p in pts)


def test_distribution_metrics_has_bands():
    k, _, kc, _ = _load_test_data()
    pts = compute_distribution_metrics(kc, k)
    for p in pts:
        assert p.band_1sigma_low_pct is not None
        assert p.band_1sigma_high_pct is not None
        assert p.band_1sigma_low_pct <= p.mean_pct <= p.band_1sigma_high_pct


def test_distribution_metrics_has_threshold_probs():
    k, _, kc, _ = _load_test_data()
    pts = compute_distribution_metrics(kc, k)
    for p in pts:
        assert p.threshold_probs is not None
        assert "gt_2_0" in p.threshold_probs
        assert "gt_2_5" in p.threshold_probs
        assert "gt_3_0" in p.threshold_probs


def test_blended_reference_points():
    k, f, kc, fc = _load_test_data()
    bc, _ = blend_curves(kc, fc, 0.55, 0.45, True, True)
    pts = compute_blended_reference_points(bc, kc, fc)
    assert len(pts) > 0
    assert all(isinstance(p, BlendedReferencePoint) for p in pts)
    for p in pts:
        assert 0 <= p.distribution_confidence_score <= 100


def test_venue_weight_diagnostics():
    k, f, kc, fc = _load_test_data()
    kd = compute_venue_weight_diagnostics("Kalshi", 0.55, k, kc)
    fd = compute_venue_weight_diagnostics("ForecastEx", 0.45, f, fc)
    assert isinstance(kd, VenueWeightDiagnostics)
    assert isinstance(fd, VenueWeightDiagnostics)
    assert kd.eligible is True
    assert fd.eligible is True
    assert 0 <= kd.raw_venue_score <= 100
    assert 0 <= fd.raw_venue_score <= 100


def test_governed_blend_weights_normalize():
    k, f, kc, fc = _load_test_data()
    kd = compute_venue_weight_diagnostics("Kalshi", 0.55, k, kc)
    fd = compute_venue_weight_diagnostics("ForecastEx", 0.45, f, fc)
    k_eff, f_eff = compute_governed_blend_weights(kd, fd)
    assert abs(k_eff + f_eff - 1.0) < 0.001, f"Weights don't sum to 1: {k_eff} + {f_eff}"


def test_ineligible_venue_gets_zero_weight():
    k, f, kc, fc = _load_test_data()
    kd = compute_venue_weight_diagnostics("Kalshi", 0.55, k, kc)
    fd = compute_venue_weight_diagnostics("ForecastEx", 0.45, f, fc)
    # Force ForecastEx ineligible
    fd.eligible = False
    k_eff, f_eff = compute_governed_blend_weights(kd, fd)
    assert f_eff == 0.0
    assert k_eff == 1.0


def test_freshness_summary_has_required_fields():
    k, _, _, _ = _load_test_data()
    fs = build_venue_freshness_summary(k, "Kalshi")
    assert isinstance(fs, VenueFreshnessSummary)
    assert fs.median_quote_age_seconds >= 0
    assert 0 <= fs.fresh_quote_fraction <= 1
    assert 0 <= fs.stale_quote_fraction <= 1


def test_blended_freshness_has_commentary():
    k, f, _, _ = _load_test_data()
    kf = build_venue_freshness_summary(k, "Kalshi")
    ff = build_venue_freshness_summary(f, "ForecastEx")
    bf = build_blended_freshness_summary(kf, ff)
    assert isinstance(bf, BlendedFreshnessSummary)
    commentary = generate_freshness_commentary(bf)
    assert len(commentary) > 20, "Commentary too short"
    assert "Kalshi" in commentary or "ForecastEx" in commentary


def test_raw_venue_score_in_range():
    score = compute_raw_venue_score(80, 70, 90, 60, 50)
    assert 0 <= score <= 100


def test_venue_scores_in_range():
    k, _, kc, _ = _load_test_data()
    assert 0 <= score_venue_liquidity(k) <= 100
    assert 0 <= score_venue_coverage(k) <= 100
    assert 0 <= score_venue_consistency(kc) <= 100
