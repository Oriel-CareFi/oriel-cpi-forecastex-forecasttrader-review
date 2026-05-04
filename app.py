"""
app.py — Oriel Prediction Index Administrator v7
Thin entrypoint: page config, CSS injection, nav bar, tab routing.
All rendering logic lives in tabs/, UI infrastructure in ui/.

Behavior is altered for the ForecastTrader external-review deployment by
``config/review_build.py``. When ``REVIEW_BUILD = True`` the app:
  * prepends an Overview tab,
  * reorders + relabels the visible tabs to match the talk-track narrative,
  * hides the Kalshi-style CPI tab, the Polymarket-style CPI tab, and the
    Index Administrator route,
  * renders an "illustrative review build" footer disclaimer.
Production behavior is restored by flipping the flag back to False.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# ── Core imports ──────────────────────────────────────────────────────────────
from sample_data import (
    HEALTHCARE_CONTRACTS_TABLE, HEALTHCARE_METHODOLOGY, HEALTHCARE_SNAPSHOTS,
)

# ── Review-build config ───────────────────────────────────────────────────────
from config.review_build import (
    REVIEW_BUILD,
    REVIEW_APP_LABEL,
    REVIEW_FOOTER,
    REVIEW_HIDDEN_TABS,
    REVIEW_TAB_ORDER,
    REVIEW_TAB_LABELS,
)

# ── Feature flags (check if venue/analytics packages are importable) ──────────
try:
    import venues.kalshi  # noqa: F401
    PHASE2_AVAILABLE = True
except ImportError:
    PHASE2_AVAILABLE = False

try:
    import parity  # noqa: F401
    PARITY_AVAILABLE = True
except ImportError:
    PARITY_AVAILABLE = False

try:
    import venues.forecastex  # noqa: F401
    FORECASTEX_AVAILABLE = True
except Exception:
    FORECASTEX_AVAILABLE = False

try:
    import venues.polymarket  # noqa: F401
    POLYMARKET_AVAILABLE = True
except Exception:
    POLYMARKET_AVAILABLE = False

try:
    import analytics.tier1_fv_engine  # noqa: F401
    import analytics.cpi_basis_diagnostics  # noqa: F401
    TIER1_AVAILABLE = True
except Exception:
    TIER1_AVAILABLE = False

try:
    import analytics.medical_basis_contract  # noqa: F401
    MEDICAL_BASIS_AVAILABLE = True
except Exception:
    MEDICAL_BASIS_AVAILABLE = False

# ── UI infrastructure ─────────────────────────────────────────────────────────
from ui.tokens import LIVE_TOGGLE_WIDGET_KEY
from ui.css import inject_css
from ui.nav import render_nav_bar
from ui.components import HC_STEPS, CPI_STEPS


from tabs.index_tab import _live_cpi_enabled
from tabs.index_admin_tab import render_index_admin_tab


# ── Page config + CSS ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title=("Oriel · ForecastTrader Review" if REVIEW_BUILD else "Oriel · Index Administrator"),
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize session state for active tab (if using sidebar nav in future)
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "hc"

# ── Production tab metadata ───────────────────────────────────────────────────
# Order + labels used when REVIEW_BUILD = False.
PRODUCTION_TAB_ORDER: tuple[str, ...] = (
    "hc", "cpi", "fx", "poly", "perp", "cms", "med_basis", "parity",
)

PRODUCTION_TAB_LABELS: dict[str, str] = {
    "hc":        "CareFi Healthcare Trend Index",
    "cpi":       "Oriel CPI Forward Index (Kalshi-style)",
    "fx":        "Oriel CPI Forward Index (ForecastEx-style)",
    "poly":      "Oriel CPI Forward Index (Polymarket-style)",
    "perp":      "Oriel CPI Basis",
    "cms":       "Oriel Healthcare Reference",
    "med_basis": "ForecastEx Medical Basis",
    "parity":    "OTC Parity Validation",
}

# Tab metadata for potential top bar use
_TAB_META = {
    "hc":     ("CareFi Healthcare Trend Index",          "Healthcare / Scalar buckets"),
    "cpi":    ("Oriel CPI Forward Index",                "Kalshi-style binary contracts"),
    "fx":     ("Oriel CPI Forward Index",                "ForecastEx-style binary thresholds"),
    "poly":   ("Oriel CPI Forward Index",                "Polymarket-style threshold contracts"),
    "perp":   ("Oriel CPI Basis",                        "Tier 1 · Spot / FV / Carry / Basis"),
    "cms":    ("Oriel Healthcare Reference",             "Healthcare cost translation layer"),
    "med_basis": ("ForecastEx Medical Basis",            "Medical inflation vs. CPI spread contracts"),
    "parity": ("OTC Parity Validation",                  "Benchmark gate · OTC CPI swap curves"),
    "overview": ("Overview",                             "ForecastTrader review build · framing"),
}

inject_css()

# ── Password gate (ForecastTrader review build) ───────────────────────────────
# Per docs/deployments/forecasttrader_password_gated_review_deployment.md:
# the deployment is a public Streamlit app gated by an in-app password
# stored in Streamlit Secrets as `review_password`. The gate is activated
# by setting the Streamlit Secret `REVIEW_BUILD = "true"` on the deployed
# app — production deployments without that secret stay open.
#
# This must run BEFORE any data loading or tab rendering so unauthenticated
# users see only the password prompt and st.stop() halts the script.
from services.review_password_gate import (
    check_review_password,
    review_build_gate_enabled,
)

if review_build_gate_enabled() and not check_review_password():
    st.stop()

# ── Pre-load CPI data ─────────────────────────────────────────────────────────
from tabs.index_tab import resolve_cpi_inputs

_use_live_cpi = bool(_live_cpi_enabled() and PHASE2_AVAILABLE and st.session_state.get(LIVE_TOGGLE_WIDGET_KEY, True))
_cpi_methodology, _cpi_snapshots, _cpi_contracts, _cpi_runtime_meta = resolve_cpi_inputs(_use_live_cpi)

# ── Top-level routing via query params ────────────────────────────────────────
active_view = st.query_params.get('view', 'main')
if isinstance(active_view, list):
    active_view = active_view[0]
active_view = active_view or 'main'

# Block the Index Administrator route entirely in the review build.
if REVIEW_BUILD and active_view == 'index_admin':
    active_view = 'main'
    try:
        st.query_params.clear()
    except Exception:
        pass

# ── Navigation bar ────────────────────────────────────────────────────────────
render_nav_bar(
    cpi_runtime_meta=_cpi_runtime_meta,
    use_live_cpi=_use_live_cpi,
    live_cpi_enabled=_live_cpi_enabled(),
    phase2_available=PHASE2_AVAILABLE,
    active_view=active_view,
    show_index_admin_link=(not REVIEW_BUILD),
    review_label=(REVIEW_APP_LABEL if REVIEW_BUILD else None),
)

# ── View routing ──────────────────────────────────────────────────────────────
if (not REVIEW_BUILD) and active_view == 'index_admin':
    render_index_admin_tab()
else:
    # ── Tab renderers (one callable per tab key) ─────────────────────────────
    from tabs import (
        render_index, render_forecastex_tab, render_polymarket_tab,
        render_perp_readiness_tab, render_cms_lag_engine_tab,
        render_medical_basis_tab, render_parity_tab, render_review_overview_tab,
    )

    # The CareFi Healthcare Trend Index tab (`hc`) is intentionally excluded
    # from the review-build sequence per
    # docs/handoffs/CPI_REVIEW_EXTERNAL_OVERVIEW_PATCH.md, but the renderer
    # is kept so production (REVIEW_BUILD = False) can still expose it.
    def _render_hc() -> None:
        render_index(
            HEALTHCARE_METHODOLOGY, HEALTHCARE_SNAPSHOTS, HEALTHCARE_CONTRACTS_TABLE,
            "Implied Healthcare Trend (%)", "%",
            "US healthcare cost trend, derived from prediction-market scalar bucket contracts.",
            HC_STEPS, "hc",
        )

    def _render_cpi() -> None:
        render_index(
            _cpi_methodology, _cpi_snapshots, _cpi_contracts,
            "Implied CPI YoY (%)", "%",
            "US CPI year-over-year, derived from Kalshi-style binary threshold and exact-outcome contracts.",
            CPI_STEPS, "cpi",
            runtime_meta=_cpi_runtime_meta,
            show_live_toggle=bool(PHASE2_AVAILABLE),
        )

    def _render_fx() -> None:
        if FORECASTEX_AVAILABLE:
            render_forecastex_tab()
        else:
            st.warning("ForecastEx modules not found. Place forecastex_*.py files in the app root directory.")

    def _render_poly() -> None:
        if POLYMARKET_AVAILABLE:
            render_polymarket_tab()
        else:
            st.warning("Polymarket modules not found. Place polymarket_*.py files in the app root directory.")

    def _render_perp() -> None:
        if TIER1_AVAILABLE:
            render_perp_readiness_tab()
        else:
            st.warning("Tier 1 engine not found. Place tier1_fv_engine.py in the analytics directory.")

    def _render_med_basis() -> None:
        if MEDICAL_BASIS_AVAILABLE:
            render_medical_basis_tab()
        else:
            st.warning("Medical basis contract module not found. Place medical_basis_contract.py in the analytics directory.")

    def _render_parity() -> None:
        if PARITY_AVAILABLE:
            render_parity_tab()
        else:
            st.warning("Parity modules not found. Place parity_*.py files in the parity directory.")

    TAB_RENDERERS: dict[str, callable] = {
        "overview":  render_review_overview_tab,
        "hc":        _render_hc,
        "cpi":       _render_cpi,
        "fx":        _render_fx,
        "poly":      _render_poly,
        "perp":      _render_perp,
        "cms":       render_cms_lag_engine_tab,
        "med_basis": _render_med_basis,
        "parity":    _render_parity,
    }

    # ── Resolve visible tab order + labels for this build ────────────────────
    if REVIEW_BUILD:
        visible_keys = [k for k in REVIEW_TAB_ORDER if k not in REVIEW_HIDDEN_TABS]
        labels = [REVIEW_TAB_LABELS.get(k, PRODUCTION_TAB_LABELS.get(k, k)) for k in visible_keys]
    else:
        visible_keys = list(PRODUCTION_TAB_ORDER)
        labels = [PRODUCTION_TAB_LABELS[k] for k in visible_keys]

    # ── Render the tab strip ─────────────────────────────────────────────────
    containers = st.tabs(labels)
    for container, key in zip(containers, visible_keys):
        with container:
            renderer = TAB_RENDERERS.get(key)
            if renderer is None:
                st.warning(f"Unknown tab key: {key}")
            else:
                renderer()

# ── Review-build footer disclaimer ────────────────────────────────────────────
# Uses the shared `note-box` class so the disclaimer matches the gold-accent
# panel language used elsewhere in the app (CMS Reference, Medical Basis tab).
if REVIEW_BUILD:
    st.markdown(
        f"""
        <div class='note-box' style='margin-top:24px;text-align:center;
                                     letter-spacing:0.02em;font-size:0.7rem;'>
          {REVIEW_FOOTER}
        </div>
        """,
        unsafe_allow_html=True,
    )
