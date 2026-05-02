# Oriel Reference Hardening Package — Developer Build Spec

## Objective
Harden the current CPI forward-reference stack so it can withstand institutional / quant scrutiny and support future downstream products:
- Oriel CPI Forward Basis Perp
- cross-market break-even comparisons
- parametric trigger structures
- corridor / collar analytics
- healthcare inflation spread products

This package focuses on two immediate upgrades:

1. **Distribution-aware curve outputs**
2. **Formal weighting engine V1**

This package **also includes quote timestamp / freshness attribution** as a first-class input and UI output, since timing mismatch can materially explain observed basis discrepancy across venues.

---

## Existing governed flow to preserve

```python
kalshi_curve = build_kalshi_curve_from_constituents(...)
forecastex_curve = build_forecastex_curve_from_constituents(...)
oriel_blended_curve = blend_curves(kalshi_curve, forecastex_curve, weights, eligibility)
snapshot = build_tier1_snapshot(oriel_blended_curve, ...)
```

### Preserve these current outputs inside **Oriel CPI Basis**
- Spot Index
- Fair Value
- Simulated Perp
- Basis
- Annualized Carry

### Add these new headline outputs
- Official Print / Base Index
- 1M implied
- 3M implied
- 6M implied
- Term Structure
- Publishability / Confidence
- Timestamp / Freshness Summary

---

# 1) Distribution-aware curve upgrade

## Goal
Move from a point-estimate-only forward curve to a governed reference object that carries basic uncertainty information.

## Scope for V1
For each venue curve and for the blended curve, compute and expose:

- `mean_pct`
- `std_dev_pct`
- `band_1sigma_low_pct`
- `band_1sigma_high_pct`
- `band_90_low_pct`
- `band_90_high_pct`
- `selected_threshold_probs`
- `constituent_dispersion_bp`
- `distribution_confidence_score`

## Notes
- Use existing binary / bucket / exact-outcome machinery where available.
- This is **not** a full higher-moment or options-style surface.
- V1 should remain audit-friendly and rule-based.

## Output object additions

### `VenueCurvePoint`
```python
@dataclass
class VenueCurvePoint:
    horizon_months: float
    mean_pct: float
    std_dev_pct: float | None
    band_1sigma_low_pct: float | None
    band_1sigma_high_pct: float | None
    band_90_low_pct: float | None
    band_90_high_pct: float | None
    threshold_probs: dict[str, float]   # e.g. {"gt_2_5": 0.41, "gt_3_0": 0.18}
    constituent_count: int
    eligible_constituent_count: int
    constituent_dispersion_bp: float | None
```

### `BlendedReferencePoint`
```python
@dataclass
class BlendedReferencePoint:
    horizon_months: float
    blended_mean_pct: float
    blended_std_dev_pct: float | None
    blended_band_1sigma_low_pct: float | None
    blended_band_1sigma_high_pct: float | None
    blended_band_90_low_pct: float | None
    blended_band_90_high_pct: float | None
    blended_threshold_probs: dict[str, float]
    source_residual_bp: dict[str, float]   # {"kalshi": +6.4, "forecastex": -6.4}
    distribution_confidence_score: float
```

## Threshold probability set for UI / analytics
Use a small fixed set, centered around the near-term CPI zone:
- `P(CPI > 2.0%)`
- `P(CPI > 2.5%)`
- `P(CPI > 3.0%)`

Make configurable via `config.py`.

## Distribution confidence score
Range: `0–100`

Suggested formula:
```python
distribution_confidence_score =
    0.30 * threshold_coverage_score +
    0.25 * distribution_consistency_score +
    0.20 * freshness_score +
    0.15 * liquidity_score +
    0.10 * interpolation_penalty_adjustment
```

---

# 2) Formal weighting engine V1

## Goal
Replace the current mostly static venue blend with a rule-based venue weighting engine by maturity / horizon.

## Principle
Separate:
- **requested weight**
- **raw score-derived weight**
- **effective post-eligibility weight**

## Venue-level score inputs
For each venue, per maturity / horizon:

### A. Liquidity score
Inputs:
- median open interest
- median volume
- median quoted depth if available
- constituent count

Suggested normalized score:
```python
liquidity_score = clamp(
    0.45 * oi_score +
    0.35 * volume_score +
    0.20 * depth_score,
    0,
    100
)
```

### B. Spread-quality score
Inputs:
- median bid/ask spread in cents
- spread as % of contract value
- crossed / locked quote penalties

Suggested:
```python
spread_quality_score = clamp(
    100
    - 35 * normalized_spread_penalty
    - 25 * stale_quote_penalty
    - 20 * crossed_quote_penalty,
    0,
    100
)
```

### C. Freshness score
Inputs:
- quote timestamp
- max quote age
- median quote age
- age dispersion across constituents

Suggested:
```python
freshness_score = clamp(
    100
    - age_minutes / freshness_half_life_minutes * 50
    - age_dispersion_penalty
    - stale_fraction_penalty,
    0,
    100
)
```

### D. Coverage score
Inputs:
- number of eligible constituents
- ladder completeness
- threshold continuity
- horizon availability

Suggested:
```python
coverage_score = clamp(
    0.40 * constituent_completeness_score +
    0.35 * ladder_continuity_score +
    0.25 * horizon_match_score,
    0,
    100
)
```

### E. Internal consistency score
Inputs:
- monotonicity violations
- residual vs fitted curve
- local convexity / shape anomalies
- threshold inversion count

Suggested:
```python
internal_consistency_score = clamp(
    100
    - 30 * inversion_penalty
    - 25 * shape_penalty
    - 20 * residual_penalty,
    0,
    100
)
```

## Raw venue score
```python
raw_venue_score =
    0.30 * liquidity_score +
    0.20 * spread_quality_score +
    0.20 * freshness_score +
    0.20 * coverage_score +
    0.10 * internal_consistency_score
```

## Eligibility rules
A venue / maturity becomes ineligible if any of the following trip:
- `median_quote_age_minutes > MAX_MEDIAN_AGE_MINUTES`
- `eligible_constituent_count < MIN_ELIGIBLE_CONSTITUENTS`
- `coverage_score < MIN_COVERAGE_SCORE`
- `internal_consistency_score < MIN_CONSISTENCY_SCORE`
- `publishability_score < MIN_PUBLISHABILITY_SCORE`

## Weight blending rule
Let:
- `requested_weight`
- `raw_score_weight = raw_venue_score / sum(raw_venue_scores among eligible venues)`

Then:
```python
blended_pre_eligibility_weight =
    blend_alpha * requested_weight +
    (1 - blend_alpha) * raw_score_weight
```

Recommended V1 default:
- `blend_alpha = 0.35`

Then:
- zero out ineligible venues
- renormalize surviving venues to 100%

## Required outputs per venue / maturity
```python
@dataclass
class VenueWeightDiagnostics:
    venue: str
    requested_weight: float
    raw_venue_score: float
    raw_score_weight: float
    effective_weight: float
    eligible: bool
    eligibility_reason: str | None
    liquidity_score: float
    spread_quality_score: float
    freshness_score: float
    coverage_score: float
    internal_consistency_score: float
```

---

# 3) Timestamp / freshness attribution (NEW REQUIRED UPGRADE)

## Why this must be included
Observed basis discrepancy can be partly explained by asynchronous quote timing between venues.

This package should make timestamp attribution explicit, not implicit.

## Required fields at constituent level
Add to each constituent row:

```python
quote_timestamp_utc: str
quote_age_seconds: float
quote_age_bucket: str              # "fresh", "aging", "stale"
exchange_timestamp_utc: str | None
ingestion_timestamp_utc: str
market_data_latency_ms: float | None
source_snapshot_id: str | None
```

## Venue summary freshness fields
```python
median_quote_age_seconds
max_quote_age_seconds
min_quote_age_seconds
stale_quote_fraction
fresh_quote_fraction
snapshot_span_seconds   # max_ts - min_ts within venue snapshot
cross_venue_timestamp_gap_seconds
```

## Blended reference freshness fields
```python
blended_snapshot_start_utc
blended_snapshot_end_utc
blended_snapshot_span_seconds
kalshi_snapshot_median_age_seconds
forecastex_snapshot_median_age_seconds
cross_venue_median_age_gap_seconds
freshness_commentary
```

## Freshness commentary examples
- "Kalshi snapshot is 18s newer than ForecastEx median constituent timestamp."
- "ForecastEx ladder includes 27% stale constituents (> 300s old)."
- "Cross-venue timestamp skew likely explains part of observed 3M basis."
- "Basis should be interpreted with caution due to 412s snapshot span."

## Timestamp display standard
- Always display **UTC timestamp**
- Also display **age in seconds / minutes**
- Show **snapshot span**
- Show **cross-venue skew**
- Avoid ambiguous "last updated" only labels

---

# 4) UI additions — exact layout for Oriel CPI Basis tab

## Top row — Reference Summary Cards
1. Official Print / Base Index
2. 1M Implied
3. 3M Implied  **(primary emphasis card)**
4. 6M Implied
5. Term Structure
6. Publishability / Confidence

### Card requirements
Each card shows:
- value
- delta vs prior close if available
- confidence icon / badge
- timestamp line

Example timestamp line:
`Snapshot: 2026-04-12 11:34:08 UTC | Age: 42s`

## Second row — Basis / Perpification Cards
Preserve existing cards:
1. Spot Index
2. Fair Value
3. Simulated Perp
4. Basis
5. Annualized Carry

### Add beneath these cards
- funding anchor note
- market regime note
- timestamp / freshness note

## Third row — Source Blend / Index Governance Panel
### Left side: Source blend table
Columns:
- Venue
- Requested Wt
- Raw Score
- Raw Score Wt
- Effective Wt
- Eligible
- Eligibility Reason
- Median Quote Age
- Snapshot Span

### Right side: Governance text block
Display:
- weighting rule
- eligibility rule
- fallback rule
- methodology version
- publication timestamp
- freshness commentary

## Fourth row — Distribution / Confidence Panel
### Left side
Chart:
- blended 1M / 3M / 6M curve
- optional venue overlays
- optional ±1 sigma band

### Right side
Mini table:
- P(CPI > 2.0%)
- P(CPI > 2.5%)
- P(CPI > 3.0%)
- blended std dev
- constituent dispersion
- distribution confidence score

## Fifth row — Timestamp / Freshness Diagnostics (NEW)
Table with:
- Venue
- Median Age
- Max Age
- Fresh %
- Stale %
- Snapshot Span
- Cross-Venue Age Gap
- Comment

Color states:
- green: healthy
- amber: moderate timing skew
- red: stale / caution

---

# 5) UI additions — venue tabs

Preserve the existing constituent-level feel in the Kalshi and ForecastEx tabs.

## Add these fields to each constituent table
- `quote_timestamp_utc`
- `quote_age_seconds`
- `quote_age_bucket`
- `effective_weight_within_venue`
- `eligibility_flag`
- `eligibility_reason`
- `spread_quality_score`
- `freshness_score`

## Add venue-level summary box
- constituent count
- eligible constituent count
- median quote age
- snapshot span
- publishability
- venue curve std dev
- selected threshold probabilities

This keeps the venue tabs as transparent methodology views.

---

# 6) Recommended config additions

```python
MAX_MEDIAN_AGE_MINUTES = 5
STALE_QUOTE_SECONDS = 300
FRESH_QUOTE_SECONDS = 60
MIN_ELIGIBLE_CONSTITUENTS = 3
MIN_COVERAGE_SCORE = 45
MIN_CONSISTENCY_SCORE = 50
MIN_PUBLISHABILITY_SCORE = 55
BLEND_ALPHA = 0.35
TARGET_THRESHOLDS = [2.0, 2.5, 3.0]
SHOW_TIMESTAMP_DIAGNOSTICS = True
```

---

# 7) File-level implementation plan against the current repo

## `tier1_fv_engine.py`
Add / update:
- `build_kalshi_curve_from_constituents(...)`
- `build_forecastex_curve_from_constituents(...)`
- `score_venue_curve(...)`
- `compute_distribution_metrics(...)`
- `blend_curves(...)`
- `build_freshness_summary(...)`
- extend `build_tier1_snapshot(...)`

## `app.py`
Update:
- `Oriel CPI Basis` tab layout
- source blend table
- distribution panel
- timestamp / freshness diagnostics panel
- upgraded card layout

## `phase2_live_data.py` / `kalshi_client.py` / `forecastex_client.py`
Add:
- constituent timestamp fields
- standardized freshness metadata
- optional exchange timestamp mapping where available

## `config.py`
Add hardening package config items.

## `tests/`
Add tests for:
- freshness scoring
- eligibility gating
- raw score to effective weight logic
- band construction
- timestamp commentary generation

---

# 8) Testing requirements

## Unit tests
- distribution metrics computed for venue curves
- weight engine scores normalize correctly
- stale venue becomes ineligible
- blended curve uses effective weights only
- timestamp gap commentary is generated correctly

## UI sanity checks
- Oriel CPI Basis tab renders with all cards
- timestamp diagnostics table renders even with one venue stale
- distribution panel renders with missing thresholds gracefully

---

# 9) Developer acceptance criteria

This package is complete when:

1. Venue tabs still show constituent-level transparency.
2. Oriel CPI Basis uses the governed blended curve.
3. 3M implied is derived from the blended venue curves.
4. Spot / FV / Simulated Perp / Basis / Carry remain visible.
5. Distribution-aware outputs are visible in UI.
6. Weighting engine outputs requested, raw, and effective weights.
7. Timestamp / freshness diagnostics are visible and explain cross-venue timing skew.
8. Publishability / confidence reflect the new weighting + freshness logic.
9. Existing app structure is preserved.

---

# 10) Why this package matters

This hardening package makes the forward curve:
- more defensible to FalconX
- more legible to quants
- more extensible for break-evens
- more useful for future parametric / collar structures
- more aligned with benchmark-governance best practice