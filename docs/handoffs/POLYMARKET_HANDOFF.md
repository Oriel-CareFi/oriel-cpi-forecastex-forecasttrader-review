# Polymarket Policy Update — Clean Drop-In Notes

This package has been tested against the current modularized codebase.

## What was updated
- Preserved the modularized architecture (`tabs/`, `ui/`, `analytics/`, `parity/`, `venues/`)
- Kept Polymarket as the 4th tab between ForecastEx and Oriel CPI Basis
- Added venue-specific Polymarket policy controls in `venues/polymarket/config.py`
- Split Polymarket logic into:
  - render eligibility for the venue tab
  - publication eligibility for official reference status
- Kept Polymarket excluded from the Oriel blend by default
- Added venue metadata to the package and tab UI:
  - `venue_role`
  - `venue_status`
  - `reference_status`
- Updated tests for the new policy behavior

## Policy defaults
- Render gate: 2 maturities minimum
- Render spread cap: 500 bp
- Preferred spread band: 250 bp
- Publication gate: 4 maturities minimum
- Publication spread cap: 150 bp
- Blend inclusion default: `False`

## Validation performed
- Python compile check passed
- Full test suite passed: 57 tests

## Files updated
- `venues/polymarket/config.py`
- `venues/polymarket/models.py`
- `venues/polymarket/client.py`
- `venues/polymarket/transform.py`
- `tabs/polymarket_tab.py`
- `tests/test_polymarket_adapter.py`
- `POLYMARKET_HANDOFF.md`

## Notes
Live Polymarket behavior still needs a deployment-environment smoke test against current production endpoints, but the package is structurally clean and test-passing in the attached codebase.
