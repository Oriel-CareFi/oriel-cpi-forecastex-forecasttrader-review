# Next phase recommendation

Included now:
- Reference-month CPI maturity parsing, with release-date fallback to prior month
- Stricter liquidity filters for live Kalshi markets
- Minimum contracts-per-maturity gate

Recommended for next phase rather than this deployment:
- OTC-comparable CPI layer and matched-object backtest tables
- Cleaner target alignment modules for realized CPI vs OTC-style transformed CPI
- Monotone spline with light regularization for constant-maturity interpolation
- Historical snapshot warehouse and evaluation dashboards

Reason: those additions change the benchmark object and methodology materially, while the current deployment goal is to harden live ingestion and avoid silent curve errors.
