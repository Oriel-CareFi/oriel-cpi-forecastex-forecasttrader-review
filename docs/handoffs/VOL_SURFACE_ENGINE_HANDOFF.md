# Volatility & Surface Engine — Developer Handoff

## What was added

This package adds a new **Volatility & Surface Engine** section to the CPI tab.

### New analytics
- `analytics/vol_surface_engine.py`
  - approximates **binary-implied vol by maturity** from threshold contracts using the parent CPI forward
  - falls back to **exact-outcome PMF dispersion** or existing curve sigma when binary inversion is unavailable
  - builds **forward-vs-vol scenario grids**
  - builds a **placeholder component-vol framework** from parent CPI vol plus beta/correlation assumptions

### New UI
- `tabs/vol_surface_tab.py`
  - renders a new section at the bottom of the CPI tab:
    - **Implied Vol Surface**
    - **Venue Dispersion**
    - **Forward / Vol Sensitivity**
    - **Component Vol Framework**

### Integration change
- `tabs/index_tab.py`
  - now calls `render_vol_surface_engine(...)` for the CPI tab only

### Test
- `tests/test_vol_surface_engine.py`
  - validates the surface artifacts build cleanly from the current demo data

## Notes for the developer
- The vol inversion is intentionally **approximate and demo-safe**, not positioned as production options analytics.
- Parent CPI forward reference is sourced from the current governed blend built off `data/kalshi_constituents_current.csv` and `data/forecastex_constituents_current.csv`.
- Venue dispersion is sourced from the existing `analytics.cpi_basis_diagnostics` flow.
- Component vols are explicitly a **placeholder framework** for roadmap discussions (medical CPI / component pricing) rather than a claim of hedge-complete market structure.

## Files changed
- `analytics/vol_surface_engine.py` **new**
- `tabs/vol_surface_tab.py` **new**
- `tabs/index_tab.py` **updated**
- `tests/test_vol_surface_engine.py` **new**
- `VOL_SURFACE_ENGINE_HANDOFF.md` **new**
