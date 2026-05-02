# FalconX Hardening Package — Developer Handoff

This package addresses the five credibility gaps most likely to be probed by a FalconX-style quant / market-structure review.

## Included changes

1. **Explicit smoothing model**
   - Added `smooth_reference_curve()` in `analytics/tier1_fv_engine.py`
   - Primary method: `liquidity_weighted_monotone_linear`
   - Fallback: `nelson_siegel_proxy` (quadratic parametric proxy under sparse coverage)
   - Exposes residuals, RMSE, max residual, monotone direction, and coverage ratio.

2. **Formal weight calibration**
   - Venue diagnostics remain score-based, but the tab now surfaces:
     - score share
     - requested share
     - effective share
     - blend rule: `effective_w = alpha * requested_w + (1-alpha) * score_w`
   - Added `compute_weight_calibration_summary()`.

3. **Explicit microstructure filtering rules**
   - Added `apply_microstructure_filters()`.
   - Introduces deterministic proxy fields for the demo dataset:
     - `proxy_spread_bp`
     - `proxy_quote_age_seconds`
     - `quote_quality_score`
     - `included_in_curve`
     - `quote_selection_reason`
   - Current demo guardrails:
     - spread gate <= 35 bp
     - staleness gate <= 300s
     - selection waterfall: tight+fresh mid -> guarded mid -> exclude

4. **Defined confidence thresholds**
   - Added `compute_enhanced_publishability()`.
   - Confidence now combines:
     - maturity coverage
     - source availability
     - weight balance
     - venue quality
     - blended freshness
   - Thresholds:
     - `Eligible / High`: >= 80
     - `Review / Moderate`: >= 65
     - `Draft / Low`: below 65

5. **Concrete trade playbook**
   - Added `generate_trade_ideas()`.
   - The CPI Basis tab now surfaces 3 practical expressions:
     - perp vs Oriel FV basis trade
     - front-end curve steepener/flattener
     - venue-quality relative-value overlay

## Files changed

- `analytics/tier1_fv_engine.py`
- `tabs/perp_readiness_tab.py`
- `tests/test_falconx_hardening.py` (new)

## Validation run

- `python -m pytest -q tests/test_falconx_hardening.py tests/test_hardening.py`
- Result: passing in local handoff package

## Notes for production/live-data follow-up

The microstructure layer currently uses deterministic proxy fields because the demo constituent CSVs do not include live bid/ask, depth, quote timestamps, or trade timestamps. The implementation was designed so those live fields can replace the proxy columns directly without changing downstream interfaces.
