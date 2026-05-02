# Brier / Historical Calibration Patch — Developer Handoff

## What this patch adds
This package adds a **historical calibration layer** to the existing Oriel CPI forward-reference stack so that prediction-market probabilities continue to drive the curve, but venue weighting and publishability now also reflect **forecast quality**, not just microstructure quality.

The patch is intentionally additive and wires into the existing stack rather than replacing it.

## Files added
- `analytics/brier_calibration.py`
- `data/calibration/venue_brier_history_sample.csv`
- `tests/test_brier_calibration_patch.py`

## Files modified
- `analytics/tier1_fv_engine.py`
- `tabs/perp_readiness_tab.py`

---

## Exact integration points

### 1) New calibration loader + summarizer
**File:** `analytics/brier_calibration.py`

This module adds:
- `load_calibration_history()`
- `compute_calibration_summary()`
- `CalibrationSummary` dataclass

It matches calibration history by:
- `venue`
- `contract_family`
- `horizon_bucket`

The current horizon buckets are:
- `0-45d`
- `46-120d`
- `121-220d`

### 2) Venue diagnostics now include calibration
**File:** `analytics/tier1_fv_engine.py`

`VenueWeightDiagnostics` now includes the following fields:
- `historical_calibration_score`
- `brier_skill_score`
- `log_loss_skill_score`
- `calibration_bias_score`
- `calibration_sample_size_score`
- `calibration_sample_size`
- `weighted_mean_brier_score`
- `weighted_mean_log_loss`
- `weighted_mean_abs_error_pct`
- `weighted_bias_pct`
- `weighted_hit_rate`
- `calibration_methodology_note`
- `contract_family_calibration`
- `horizon_bucket_calibration`

### 3) Where calibration is wired into the score stack
**File:** `analytics/tier1_fv_engine.py`

#### A. `compute_venue_weight_diagnostics(...)`
Now optionally accepts:
- `calibration_df: pd.DataFrame | None = None`

If omitted, it defaults to:
- `load_calibration_history()`

This function now computes a `CalibrationSummary` and injects it into `VenueWeightDiagnostics`.

#### B. `compute_raw_venue_score(...)`
Now includes:
- `historical_calibration: float = 50.0`

Updated weight stack:
- 25% liquidity
- 15% spread quality
- 15% freshness
- 15% coverage
- 10% internal consistency
- 20% historical calibration

Formula:

```python
raw_score = (
    0.25 * liquidity +
    0.15 * spread +
    0.15 * freshness +
    0.15 * coverage +
    0.10 * consistency +
    0.20 * historical_calibration
)
```

#### C. Eligibility gating
New minimum added:
- `MIN_HISTORICAL_CALIBRATION_SCORE = 40.0`

So venue eligibility now fails if the calibration score is below threshold, just like coverage / consistency.

#### D. `compute_weight_calibration_summary(...)`
Now surfaces:
- venue historical calibration score
- weighted mean Brier score by venue
- calibration sample size by venue

This is what the CPI Basis tab uses to show the new calibration panel content.

#### E. `compute_enhanced_publishability(...)`
Confidence score now includes a dedicated calibration component.

Updated confidence stack:
- 20% maturity score
- 15% source score
- 10% balance score
- 20% quality score
- 20% freshness score
- 15% calibration score

This prevents calibration from being buried entirely inside the venue raw score.

---

## Calibration data schema
**File:** `data/calibration/venue_brier_history_sample.csv`

Required fields:
- `venue`
- `contract_family`
- `horizon_bucket`
- `horizon_min_days`
- `horizon_max_days`
- `n_obs`
- `mean_brier_score`
- `mean_log_loss`
- `mean_abs_error_pct`
- `hit_rate`
- `bias_pct`
- `last_updated`
- `source`

### Recommended production extension
In production, backfill this table from realized contract outcomes with one row per:
- venue
- contract family
- horizon bucket
- release family or regime slice (optional but recommended)

You can later extend grouping by:
- headline CPI vs medical CPI
- exact-outcome vs threshold ladder
- venue-specific market format
- macro regime buckets

---

## How the calibration score is computed
Inside `compute_calibration_summary()`:

### Subscores
- **Brier skill score**: normalized against the binary worst-case baseline of `0.25`
- **Log-loss skill score**: normalized against the coin-flip baseline of `0.6931`
- **Bias score**: penalty for persistent over/under-confidence
- **Sample size score**: log-scaled reward for larger realized history

### Composite historical calibration score
```python
historical_score = (
    0.45 * brier_skill +
    0.20 * log_skill +
    0.15 * bias_score +
    0.20 * sample_score
)
```

This score is then used in:
1. venue raw score
2. eligibility gating
3. enhanced publishability / confidence

---

## UI wiring
**File:** `tabs/perp_readiness_tab.py`

The Calibration / Trade Playbook panel now surfaces:
- historical calibration score by venue
- weighted Brier by venue
- calibration sample size by venue
- confidence breakdown includes calibration score

No existing UI pathways were removed.

---

## Why this implementation is intentionally conservative
This patch uses Brier / log-loss as a **trust and calibration layer**, not a direct curve-level override.

That means:
- market probabilities still drive the forward curve
- calibration influences **how much trust** the methodology places on each venue / contract family / horizon bucket
- the system remains interpretable for institutional users

This is the right structure for Oriel:
- **Observed curve** = market-implied signal
- **Reference curve** = governed, weighted blend
- **Confidence / publishability** = microstructure + historical calibration

---

## What to do next in production
1. Replace sample CSV with a real realized-outcomes backfill.
2. Add release-family keys if you want separate calibration for CPI, core CPI, medical CPI, etc.
3. Add regime-aware slices if you want stress-vs-normal calibration.
4. Consider horizon-sensitive weighting so farther-dated contracts rely relatively more on calibration and coverage than raw freshness.
5. Optionally add a contract-level calibration residual panel in the Index Administrator view.

---

## Test coverage
Added test file:
- `tests/test_brier_calibration_patch.py`

It verifies:
- calibration history loads
- calibration summaries populate correctly
- venue diagnostics carry calibration fields
- weight calibration summary exposes the new Brier/calibration fields

