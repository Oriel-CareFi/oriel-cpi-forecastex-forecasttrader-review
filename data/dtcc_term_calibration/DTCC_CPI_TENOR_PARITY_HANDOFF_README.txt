DTCC CPI Tenor Parity Developer Handoff
======================================

Objective
---------
Move from monthly 'target_month' parity to tenor-based OTC term-rate parity.

Why
---
The DTCC SDR CPI swap dataset is dominated by tenor-based inflation swaps (e.g. 1Y, 2Y, 5Y, 10Y, 30Y),
not monthly CPI buckets. These trades should not be forced into a monthly target_month schema.

Recommended join
----------------
Join Oriel and DTCC on:
- target_tenor_months (primary)
- target_tenor_label (secondary / display)

Recommended comparison
----------------------
Compare:
- DTCC observed_rate_pct
vs
- Oriel oriel_term_rate_pct

Core files
----------
1. dtcc_cpi_tenor_parity_trade_input.csv
   Trade-level normalized DTCC tenor-parity input.

2. dtcc_cpi_tenor_parity_summary_input.csv
   By-tenor summary for direct calibration / dashboard use.

3. dtcc_cpi_tenor_parity_monthly_summary_input.csv
   Execution-month by tenor summary.

4. oriel_term_parity_template.csv
   Empty template for Oriel term-rate output in the same join schema.

5. dtcc_cpi_tenor_parity_schema.json
   Explicit schema and join guidance.

Suggested parity outputs
------------------------
For each tenor:
- absolute_basis_bp = 100 * (oriel_term_rate_pct - observed_rate_pct)
- squared_error_bp2
- notional_weighted_basis_bp
- trade_count
- within_tolerance flags (e.g. +/-10bp, +/-25bp)

Notes
-----
- This handoff is for term-rate parity, not monthly parity.
- cpi_lag_months is inferred conventionally and should be treated as inferred, not explicit.
- Oddball tenors (e.g. 43M, 27Y) are preserved in the DTCC summaries for auditability.
- For presentation, standard tenors can be filtered to 1Y / 2Y / 3Y / 5Y / 10Y / 30Y.