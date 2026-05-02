# Oriel Prediction Index Administrator — v28-ft-review.3

A production-grade Streamlit dashboard for prediction-market-based CPI forward indices. Live data from Kalshi, ForecastEx, and Polymarket with automatic fallback to sample data. Includes OTC parity validation, DTCC term-structure calibration, a governed-blend CPI Basis layer, a CMS-anchored Healthcare Reference, an illustrative ForecastEx-style medical inflation basis contract, and a governed Index Administrator view.

> **This branch (`forecasttrader-review`) is the external-review build for ForecastEx / ForecastTrader.**
> Two independent gates control review-build behavior:
>   * `config/review_build.py` (Python) flips `REVIEW_BUILD = True` to prepend the Overview tab, reorder + relabel tabs to the talk-track narrative, hide the Kalshi-style CPI tab, the Polymarket-style CPI tab, and the Index Administrator route, and render the "illustrative review build" footer disclaimer.
>   * Streamlit Secret `REVIEW_BUILD = "true"` activates the in-app password gate (`services/review_password_gate.py`). The deployed app is **public** with **password-gated content** — the workaround for Streamlit Community Cloud's one-private-app-per-workspace limit.
>
> Set both back to False / unset to restore the full eight-tab production experience.
> Production deployment lives on the `main` branch.

**Production demo:** [kalshi-inflation-index-demo-personal.streamlit.app](https://kalshi-inflation-index-demo-personal-2kopxqevr5x2rg6qtxkdmy.streamlit.app/)
**Review deployment (public, password-gated):** `https://oriel-cpi-forecasttrader.streamlit.app`

---

## Tabs

Order shown is the **review build** (talk-track narrative). Production order on `main` follows the original eight-tab layout.

| Order | Tab | Purpose | Visible in review build? |
|---|---|---|---|
| 1 | Overview | 30-45 second framing — CPI as on-ramp, healthcare as differentiated module | Review only |
| 2 | ForecastEx CPI Forward Index | Live CPI forward curve from ForecastEx binary threshold contracts | Yes |
| 3 | CPI Basis · Cross-Venue Diagnostics | Governed-blend reference layer — spot / FV / carry / basis with venue diagnostics | Yes |
| 4 | Medical CPI Tracker · Healthcare Reference | Healthcare cost trend from scalar bucket prices + Medical CPI Monitor | Yes |
| 5 | ForecastEx Medical Inflation Basis Contract | Illustrative ForecastEx-style spread contracts on Medical CPI YoY − CPI-U YoY | Yes |
| 6 | CMS Reference (backup) | CMS-anchored healthcare cost translation with trading / hedging / benchmark sub-tabs | Yes (backup) |
| 7 | OTC Parity Validation (backup) | Benchmark comparison vs cleaned OTC CPI swap curves + DTCC live term calibration | Yes (backup) |
| — | Oriel CPI Forward Index (Kalshi-style) | Live CPI forward curve from Kalshi binary-outcome contracts | **Hidden** |
| — | Oriel CPI Forward Index (Polymarket-style) | Live CPI forward curve from Polymarket threshold contracts | **Hidden** |
| — | Index Administrator | Governed reference construction, publication controls, audit trail | **Hidden** (route blocked) |

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. Default mode is sample data. Set `KALSHI_ENABLE_LIVE_CPI=true` in `.env` to enable live Kalshi polling.

---

## Live vs Sample Data

| Mode | How to enable | Behavior |
|---|---|---|
| Sample | Omit config or set `KALSHI_ENABLE_LIVE_CPI=false` | Static demo data from `sample_data.py`. Fully offline. |
| Live Kalshi | `KALSHI_ENABLE_LIVE_CPI=true` | Polls Kalshi public REST API (cache TTL from `KALSHI_CACHE_SECONDS`, default 60s) |
| Live ForecastEx | Auto-discovered from `FORECASTEX_DATA_PAGE_URL` | Polls ForecastEx pairs CSV feed; toggle in-tab |
| Live Polymarket | `POLYMARKET_ENABLE_LIVE=true` | Polls Polymarket Gamma API for CPI threshold markets |

Healthcare tab is always sample data. On any live-feed failure the app falls back to sample data and shows a warning banner — it never crashes.

---

## Environment Configuration

Create `.env` beside `app.py`. Do not commit it (see `.gitignore`).

### Kalshi

| Variable | Default | Description |
|---|---|---|
| `KALSHI_ENABLE_LIVE_CPI` | `false` | Enable live feed |
| `KALSHI_CPI_SERIES_TICKER` | `KXCPI` | CPI series ticker |
| `KALSHI_API_BASE_URL` | `elections.kalshi.com` | Primary REST endpoint |
| `KALSHI_API_BASE_URL_FALLBACK` | `trading-api.kalshi.com` | Fallback host |
| `KALSHI_CACHE_SECONDS` | `60` | Cache TTL |
| `KALSHI_MIN_OPEN_INTEREST` | `25` | Contract inclusion threshold |
| `KALSHI_MIN_VOLUME` | `10` | Contract inclusion threshold |
| `KALSHI_MAX_WIDE_SPREAD` | `0.20` | Max bid-ask spread |
| `KALSHI_MAX_MATURITIES` | `6` | Max forward-curve maturities |
| `KALSHI_TIMEOUT_SECONDS` | `20` | Per-request timeout |
| `KALSHI_MAX_RETRIES` | `6` | HTTP retry attempts |

### ForecastEx

| Variable | Default | Description |
|---|---|---|
| `FORECASTEX_DATA_PAGE_URL` | `https://forecastex.com/data` | Data page for CSV auto-discovery |
| `FORECASTEX_INTRADAY_PAIRS_URL` | *(auto)* | Pin a specific pairs CSV URL |
| `FORECASTEX_MIN_VOLUME` | `1` | Contract inclusion threshold |
| `FORECASTEX_MAX_CURVE_POINTS` | `6` | Max forward-curve maturities |
| `FORECASTEX_STALE_AFTER_MINUTES` | `20` | Freshness timeout |

### Polymarket

| Variable | Default | Description |
|---|---|---|
| `POLYMARKET_ENABLE_LIVE` | `false` | Enable live Gamma API |
| `POLYMARKET_MAX_SPREAD_BP` | `35` | Contract inclusion threshold |
| `POLYMARKET_STALE_AFTER_HOURS` | `36` | Freshness timeout |

---

## Deploy to Streamlit Cloud

1. Push to a GitHub repo
2. At [share.streamlit.io](https://share.streamlit.io) → **New app**, point it at `app.py`
3. **App settings → Secrets**, paste the contents of `secrets.toml.example`
4. **Deploy** — no other changes needed

---

## Project Structure

```
oriel_demo_v7/
├── app.py                     # Thin entrypoint — page config, CSS, nav, routing
├── engine.py                  # Core curve engine (PredictionIndexAdmin, isotonic regression)
├── sample_data.py             # Static fallback data
│
├── ui/                        # Shared UI infrastructure
│   ├── tokens.py              # Design tokens (colors, radii, table dims)
│   ├── css.py                 # CSS loader (reads assets/oriel.css, interpolates tokens)
│   ├── plotly_theme.py        # ORIEL_TEMPLATE + PLOTLY_CONFIG
│   ├── tables.py              # _plotly_desk_table + height helpers
│   ├── charts.py              # _layout, make_forward_curve, make_distribution
│   ├── nav.py                 # Top nav bar, logo, badges, Index Administrator link
│   └── components.py          # HC_STEPS, CPI_STEPS methodology definitions
│
├── tabs/                      # One renderer per tab
│   ├── index_tab.py           # Healthcare + Kalshi CPI
│   ├── forecastex_tab.py
│   ├── polymarket_tab.py
│   ├── perp_readiness_tab.py  # CPI Basis
│   ├── cms_tab.py             # Healthcare Reference
│   ├── parity_tab.py          # OTC Parity + Term Calibration
│   └── index_admin_tab.py     # Index Administrator view
│
├── venues/                    # Venue adapters (config / client / models / transform)
│   ├── kalshi/
│   ├── forecastex/
│   └── polymarket/
│
├── analytics/                 # Engine & analysis modules
│   ├── tier1_fv_engine.py           # Governed blend + weighting engine + freshness
│   ├── cpi_basis_diagnostics.py     # Venue diagnostics
│   ├── cms_lag_loader.py            # Healthcare pipeline loader
│   └── dtcc_term_calibration.py     # DTCC tenor calibration loader
│
├── parity/                    # OTC parity pipeline
├── index_admin/               # Index Administrator dataclass models
├── services/                  # Index Administrator service layer
├── assets/                    # oriel.css, oriel_logo.png
├── data/                      # CSVs + pipeline artifacts
├── tests/                     # pytest suite
└── .streamlit/, requirements.txt, runtime.txt, secrets.toml.example, .gitignore
```

Import layering is strict and acyclic: `ui.tokens` → `ui.*` → `tabs.*` → `app.py`. Each tab is independently editable. CSS lives in `assets/oriel.css` and is cached via `@st.cache_resource`.

---

## FalconX Hardening Layer (v24)

Five credibility upgrades to the CPI Basis reference stack, targeting institutional / quant review:

| Layer | Function | What it does |
|---|---|---|
| Smoothing model | `smooth_reference_curve()` | Liquidity-weighted monotone linear + Nelson-Siegel proxy fallback; exposes residuals, RMSE, monotone direction |
| Weight calibration | `compute_weight_calibration_summary()` | Surfaces score share, requested share, effective share per venue with full blend-rule transparency |
| Microstructure filters | `apply_microstructure_filters()` | Deterministic proxy fields (spread gate ≤ 35bp, staleness ≤ 300s, selection waterfall); structured for live-field swap |
| Enhanced publishability | `compute_enhanced_publishability()` | Combines maturity coverage, source availability, weight balance, venue quality, blended freshness → Eligible/Review/Draft |
| Trade playbook | `generate_trade_ideas()` | 3 practical expressions: perp vs FV basis, front-end steepener/flattener, venue-quality RV overlay |

Microstructure proxy fields (`proxy_spread_bp`, `proxy_quote_age_seconds`, `quote_quality_score`, `included_in_curve`, `quote_selection_reason`) are deterministic stand-ins for the demo CSVs — swap for real venue fields when live bid/ask, depth, and timestamps are available.

---

## Volatility & Surface Engine (v25)

Renders at the bottom of the CPI tab. Approximate binary-implied vol from threshold contracts using the parent CPI forward reference.

| Section | What it shows |
|---|---|
| Implied Vol Surface | Binary-implied vol by maturity; falls back to exact-outcome PMF dispersion or curve sigma |
| Venue Dispersion | Cross-venue vol dispersion sourced from `cpi_basis_diagnostics` |
| Forward / Vol Sensitivity | Forward-vs-vol scenario grid |
| Component Vol Framework | Placeholder component-vol from parent CPI vol + beta/correlation assumptions (roadmap item) |

Engine: `analytics/vol_surface_engine.py` (237 lines). Tab renderer: `tabs/vol_surface_tab.py` (188 lines). Demo-safe approximation — not positioned as production options analytics.

---

## Medical CPI Monitor (v26)

Live BLS medical-CPI tracker added to the **CareFi Healthcare Trend Index** tab. Fetches 7 official BLS series via the public v2 time-series API with automatic fallback to a local seed CSV.

| Series | BLS ID |
|---|---|
| Medical care | CUUR0000SAM |
| Medical care services | CUUR0000SAM2 |
| Medical care commodities | CUUR0000SAM1 |
| Physicians' services | CUUR0000SEMC01 |
| Hospital services | CUUR0000SEMD01 |
| Prescription drugs | CUUR0000SEMF01 |
| Health insurance | CUUR0000SEME |

**What renders:**
- Signal-vs-print gap (Oriel front anchor vs latest official medical care Y/Y)
- Three breadth cards: accelerating share, weighted share above 3%, cross-sectional dispersion
- Monthly Medical CPI Tracker desk table (M/M, Y/Y, Prev Y/Y, Weight, BLS Series)
- Breadth methodology panel

Engine: `analytics/medical_cpi_tracker.py`. Seed data: `data/medical_cpi_tracker/medical_cpi_seed.csv`. All series are unadjusted CPI-U U.S. city average.

---

## ForecastEx Medical Basis Contract (v28)

New top-level tab — **ForecastEx Medical Basis** — adds an illustrative spread-contract layer:

```text
Medical CPI YoY − CPI-U YoY > threshold_bps
```

| Component | What it does |
|---|---|
| `analytics/medical_basis_contract.py` | `MedicalBasisContractSpec`, `ReferenceLeg`, threshold ladder → bucket distribution, expected basis, objective settlement calculator |
| `data/medical_basis_sample_contracts.csv` | 4 maturities × 5 thresholds (0/100/200/300/400 bps), illustrative ForecastEx-style YES prices with bid/ask/volume/OI |
| `tabs/medical_basis_tab.py` | UI tab — page header, 3 reference-leg cards, KPI strip, Contract Spec table, Objective Settlement Calculator, threshold ladder / implied distribution / basis curve charts, Sample Contract Ladder desk table |
| `tests/test_medical_basis_contract.py` | 7 tests — sample loads, distribution sums to 1, monotonic repair, basis curve build, slide-aligned settlement (5.6% medical vs. 3.1% CPI = 250 bps spread > 200 bps → YES / $1.00), no-settle case, contract-spec dataframe |

Settlement direction: spread > threshold settles YES at $1.00. Monotonic repair on the YES-price ladder is built in to prevent negative bucket probabilities.

**Phase II hook**: drop in a venue adapter for `tabs/medical_basis_tab.py` returning the same normalized fields (maturity, threshold_bps, yes_price, bid, ask, volume, open_interest, source_status, contract_label) and the UI/engine continues unchanged.

---

## ForecastTrader Review Build (v28-ft-review.0)

External-review deployment for ForecastEx / ForecastTrader principals. Same code as production; behavior is gated by a single flag in `config/review_build.py`.

| Component | What it does |
|---|---|
| `config/review_build.py` | Single source of truth — `REVIEW_BUILD`, `REVIEW_AUDIENCE`, `REVIEW_APP_LABEL`, `REVIEW_FOOTER`, `REVIEW_HIDDEN_TABS`, `REVIEW_TAB_ORDER`, `REVIEW_TAB_LABELS` |
| `tabs/overview_tab.py` | Talk-track Overview tab (review-build only) — header chip, KPI strip, narrative pillars, walkthrough timeline, audience lens, close/ask preview |
| `app.py` | Reads the flag, builds the visible tab list, blocks the `?view=index_admin` query route, swaps the Index Administrator nav link for a review-build label, renders the disclaimer footer |
| `ui/nav.py` | `render_nav_bar(..., show_index_admin_link=False, review_label="Oriel CPI Demo — ForecastTrader Review")` |
| `docs/deployments/forecasttrader_review_deployment.md` | Original handoff doc — branch, subdomain, sanitization checklist, smoke-test plan, rollback |

**Visible tab order in review mode:** Overview → ForecastEx CPI → CPI Basis → Medical CPI Tracker → Medical Basis Contract → CMS (backup) → OTC Parity (backup).

**Hidden in review mode:** Oriel CPI (Kalshi-style), Oriel CPI (Polymarket-style), Index Administrator.

**Footer disclaimer (every tab):** *Oriel CPI Demo · Illustrative review build for ForecastTrader · Not production trading infrastructure.*

To return to the production layout: set `REVIEW_BUILD = False` in `config/review_build.py`. No tab renderer changes needed.

### Password gate (v28-ft-review.2)

Streamlit Community Cloud allows only one private app per workspace and the production app already occupies that slot. Per `docs/deployments/forecasttrader_password_gated_review_deployment.md`, the review build is therefore deployed as a **public** Streamlit app with an in-app password gate.

| Component | What it does |
|---|---|
| `services/review_password_gate.py` | `check_review_password()` (uses `hmac.compare_digest`) and `review_build_gate_enabled()` (reads the `REVIEW_BUILD` Streamlit Secret) |
| `app.py` | Calls the gate immediately after `inject_css()`, before any data loading or tab rendering. Calls `st.stop()` on failed auth so unauthenticated users see only the prompt. |

**Required Streamlit Secrets for the deployed review app:**

```toml
KALSHI_ENABLE_LIVE_CPI = "false"
POLYMARKET_ENABLE_LIVE = "false"

review_password = "<set-a-strong-password>"
REVIEW_BUILD    = "true"

[review]
audience = "ForecastTrader"
build    = "external_review"
```

The password is **never** committed to the repo — it lives only in the Streamlit Cloud Secrets panel. The `REVIEW_BUILD` secret is what activates the gate; setting it to anything other than `"true"` (or omitting it) leaves the app open. This means the same code on `main` won't accidentally lock out the production app even if the branch is merged.

---

## Brier / Historical Calibration Layer (v27)

Adds forecast-quality scoring to the venue weighting and publishability stack. Prediction-market probabilities still drive the curve, but venue trust now also reflects historical calibration accuracy.

| Component | What it does |
|---|---|
| `analytics/brier_calibration.py` | Loads calibration history, computes per-venue Brier skill, log-loss skill, bias, sample-size scores |
| Venue raw score | Now 25% liquidity + 15% spread + 15% freshness + 15% coverage + 10% consistency + **20% historical calibration** |
| Eligibility gating | New minimum: `historical_calibration_score >= 40` |
| Enhanced publishability | Confidence stack now includes a dedicated 15% calibration component |
| UI (CPI Basis tab) | Weight calibration panel surfaces historical calibration score, weighted Brier, and sample size per venue |

Calibration data: `data/calibration/venue_brier_history_sample.csv` — sample backfill scaffold (12 rows, 2 venues × 2 contract families × 3 horizon buckets). Replace with real realized-outcomes history in production.

---

## Architecture

```
.env / Streamlit Secrets
        │
        ▼
   Venue configs  (Kalshi / ForecastEx / Polymarket)
        │
        ▼
   Venue clients  (REST, retries, fallback to sample)
        │
        ▼
   build_live_*_feed() / score_and_package()     parse → filter → normalize
        │
        ▼
   List[MaturitySnapshot] / CurvePackage         engine-ready inputs
        │
        ▼
   PredictionForwardCurve / Tier1Snapshot        curve engine + FV interpolation
   (engine.py / analytics/tier1_fv_engine.py)
        │
        ▼
   Streamlit UI  (app.py + tabs/*)
```

### Governed Blend (CPI Basis)

```
kalshi_constituents_current.csv      forecastex_constituents_current.csv
          │                                    │
  build_kalshi_curve(...)             build_forecastex_curve(...)
          │                                    │
          └──────────> blend_curves() <────────┘
                       (weighting engine V1: liquidity 30% + spread 20%
                        + freshness 20% + coverage 20% + consistency 10%)
                                │
                      build_tier1_snapshot()
                                │
                   ORIEL 3M CPI FORWARD INDEX strip
                   + Source Blend / Index Governance panel
```

### Index Administrator

Routed via `?view=index_admin` (click the "INDEX ADMINISTRATOR" link in the top nav). Five sub-tabs:

- **Index Definition** — metadata, maturity coverage, publication record
- **Eligibility & Inputs** — observation table with venue filters and eligibility flags
- **Calculation Engine** — curve comparison (market-implied / blended / fair value) + venue weight + publishability bar
- **Publication Controls** — quality-score breakdown, decision thresholds, override status
- **Audit Trail** — run history, fallback hierarchy usage, latest publication record

Data computed from `data/kalshi_constituents_current.csv` + `data/forecastex_constituents_current.csv` + `data/oriel_curve_current.csv` via `services/index_admin.py`. Dataclass models in `index_admin/models.py`.

---

## Data Files

### Constituent & curve inputs
- `kalshi_constituents_current.csv` / `_prior.csv`
- `forecastex_constituents_current.csv` / `_prior.csv`
- `oriel_curve_current.csv` / `_prior.csv` / `_sample.csv`

### OTC parity benchmarks
- `otc_cpi_quotes_tighter_demo.csv` — expected PASS
- `dtcc_cpi_static_demo_2026Q2.csv` — expected PASS (DTCC SDR format)
- `otc_cpi_quotes_negative_control.csv` — expected FAIL (stress case)

### Healthcare Reference pipeline artifacts (`data/cms_lag_engine/`)
- `basis_action_panel.csv` — current basis, percentile, convergence window, lens
- `cms_anchor_timeseries.csv` — yearly public rail / Oriel spot / CMS anchor / basis
- `service_line_signal_panel.csv` — physician / IP-OP RV sleeve gaps
- `historical_benchmark_panel.csv` — year-by-year translated signal vs official anchor
- `provenance_manifest.json` — parsed inputs and pipeline outputs

### DTCC term calibration (`data/dtcc_term_calibration/`)
- `dtcc_cpi_tenor_parity_summary_input.csv` — tenor bucket summary
- `dtcc_cpi_tenor_parity_monthly_summary_input.csv` — month × tenor breakdown
- `dtcc_cpi_tenor_parity_trade_input.csv` — trade-level data
- `oriel_term_parity_template.csv` — template for Option B term-parity build

---

## Index Administrator · Reference Construction

Publication decision thresholds (enforced by the service layer):

| Decision | Publishability score | Action |
|---|---|---|
| Publish | ≥ 0.80 | Full publication |
| Restricted | 0.65 – 0.80 | Diagnostic only |
| Hold | < 0.65 | Withheld |

Publishability score weighting: quality 30% + timestamp integrity 20% + source diversity 20% + fallback penalty 15% + continuity 15%.

---

## OTC Parity Validation

Three scenarios ship with the demo:

| Scenario | Benchmark | Expected |
|---|---|---|
| Reference OTC Benchmark | `otc_cpi_quotes_tighter_demo.csv` | PASS — avg ~4.5 bp |
| DTCC SDR Calibration Sample | `dtcc_cpi_static_demo_2026Q2.csv` | PASS |
| Out-of-Tolerance Stress Case | `otc_cpi_quotes_negative_control.csv` | FAIL |

Gate thresholds: avg abs basis ≤ 10 bp, max abs basis ≤ 10 bp, ≥ 100% within ±10 bp, index R² ≥ 0.95.

A separate **Term Calibration (DTCC Live)** sub-tab surfaces real DTCC SDR public CPI swap data (1Y / 2Y / 3Y / 5Y / 10Y / 30Y) as an institutional reference anchor — reference only, not a parity gate, because tenor-based ZCIS/YYIS trades don't analytically map to single monthly CPI buckets.

---

## Testing

```bash
pytest tests/
```

Covers the curve engine, venue adapters (Kalshi / ForecastEx / Polymarket), weighting engine, timestamp freshness attribution, parity pipeline, and CMS loader.

---

## Configuration Notes

- **OTC parity thresholds**: avg / max ≤ 10 bp, 100% within ±10 bp, R² ≥ 0.95
- **Blend defaults (CPI Basis)**: Kalshi 55% / ForecastEx 45%, alpha 0.35 between requested and score-derived weights, ineligible venues zeroed and renormalized
- **Polymarket policy**: classified as a Diagnostic / Supplemental Venue — two-layer eligibility (Render gate 2+ maturities, Publication gate 4+ maturities); not included in Oriel blend by default
