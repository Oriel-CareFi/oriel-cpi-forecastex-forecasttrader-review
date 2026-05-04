"""
config/review_build.py — ForecastTrader review-build flag.

Toggling REVIEW_BUILD = True causes app.py to:
  * Render the App Overview tab (external-facing, see
    tabs/review_overview_tab.py) as the first tab.
  * Reorder + relabel the visible tabs to match the external review
    layout requested by Chris in the CPI_REVIEW_EXTERNAL_OVERVIEW_PATCH
    handoff.
  * Block the ?view=index_admin query route.
  * Render a disclaimer footer at the bottom of every page.
  * Replace the Index Administrator nav link with the review-build
    label.

Per the v28-ft-review.5 update: Kalshi-style and Polymarket-style CPI
tabs are now visible (Chris listed them in the acceptance criteria as
distinct CPI Forward Index methodologies, not competing venues). The
CareFi Healthcare Trend Index (`hc`) tab is dropped from the external
sequence to keep the app focused on the CPI-to-healthcare workflow.

Flip REVIEW_BUILD = False on the production branch (`main`) to restore
the full eight-tab production experience and re-enable Index Admin.

This module is the single source of truth for review-build behavior.
No tab renderer reads it directly; it is consumed only by app.py.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Master flag — controls whether this build behaves as the external-review
# deployment for ForecastEx / ForecastTrader principals.
# ─────────────────────────────────────────────────────────────────────────────
REVIEW_BUILD: bool = True

# ─────────────────────────────────────────────────────────────────────────────
# External-facing labels.
# ─────────────────────────────────────────────────────────────────────────────
REVIEW_AUDIENCE: str = "ForecastTrader"
REVIEW_APP_LABEL: str = "Oriel CPI Demo — ForecastTrader Review"
REVIEW_FOOTER: str = (
    "Oriel CPI Demo · Illustrative review build for ForecastTrader · "
    "Not production trading infrastructure"
)

# ─────────────────────────────────────────────────────────────────────────────
# Tab visibility / ordering.
#
# Tab keys (must match the keys in app.py's TAB_RENDERERS):
#   overview  — App Overview (external-facing review_overview_tab)
#   cpi       — Oriel CPI Forward Index (Kalshi-style)
#   fx        — Oriel CPI Forward Index (ForecastEx-style)
#   poly      — Oriel CPI Forward Index (Polymarket-style)
#   perp      — Oriel CPI Basis
#   cms       — Medical CPI Tracker (renders render_cms_lag_engine_tab)
#   med_basis — ForecastEx Medical Basis
#   parity    — OTC Parity Validation
#
# `hc` (CareFi Healthcare Trend Index) is intentionally excluded from
# the review-build sequence per CPI_REVIEW_EXTERNAL_OVERVIEW_PATCH.
# ─────────────────────────────────────────────────────────────────────────────
REVIEW_HIDDEN_TABS: tuple[str, ...] = ()

# Order in which the visible tabs are rendered in the review build.
# Matches the acceptance criteria in
# docs/handoffs/CPI_REVIEW_EXTERNAL_OVERVIEW_PATCH.md.
REVIEW_TAB_ORDER: tuple[str, ...] = (
    "overview",
    "cpi",
    "fx",
    "poly",
    "perp",
    "cms",
    "med_basis",
    "parity",
)

# Tab labels overridden for the review build.
# Any key not present here falls back to its production label.
REVIEW_TAB_LABELS: dict[str, str] = {
    "overview":  "App Overview",
    "cpi":       "Oriel CPI Forward Index (Kalshi-style)",
    "fx":        "Oriel CPI Forward Index (ForecastEx-style)",
    "poly":      "Oriel CPI Forward Index (Polymarket-style)",
    "perp":      "Oriel CPI Basis",
    "cms":       "Medical CPI Tracker",
    "med_basis": "ForecastEx Medical Basis",
    "parity":    "OTC Parity Validation",
}
