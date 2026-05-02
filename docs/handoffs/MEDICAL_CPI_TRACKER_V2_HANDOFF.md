# Medical CPI Tracker v2 — Developer Handoff

## What changed
- Added live BLS API fetch for the monthly Medical CPI panel with automatic fallback to a local seed CSV.
- Added a new **Medical CPI Monitor** section on the **CareFi Healthcare Trend Index** tab.
- Added three first-pass breadth cards:
  - Accelerating share
  - Weighted share above 3%
  - Cross-sectional dispersion

## Files added
- `analytics/medical_cpi_tracker.py`
- `data/medical_cpi_tracker/medical_cpi_seed.csv`
- `tests/test_medical_cpi_tracker.py`
- `MEDICAL_CPI_TRACKER_V2_HANDOFF.md`

## Files changed
- `tabs/index_tab.py`

## Series wired to live BLS fetch
- Medical care — `CUUR0000SAM`
- Medical care services — `CUUR0000SAM2`
- Medical care commodities — `CUUR0000SAM1`
- Physicians' services — `CUUR0000SEMC01`
- Hospital services — `CUUR0000SEMD01`
- Prescription drugs — `CUUR0000SEMF01`
- Health insurance — `CUUR0000SEME`

## Notes
- Uses the BLS public v2 time-series API.
- All series are unadjusted CPI-U U.S. city average so the panel remains internally consistent, including health insurance.
- If the live call fails, the app silently falls back to `data/medical_cpi_tracker/medical_cpi_seed.csv`.
- Breadth weights are seeded from BLS relative-importance style weights currently embedded in `SERIES_CONFIG`.
- Threshold for the weighted breadth card is currently `3.0%` and can be changed in `analytics/medical_cpi_tracker.py`.

## Quick test
- `pytest -q tests/test_medical_cpi_tracker.py`
