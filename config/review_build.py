"""
config/review_build.py — ForecastTrader review-build flag.

Toggling REVIEW_BUILD = True causes app.py to:
  * Render the Overview tab as the first tab.
  * Reorder + relabel the visible tabs to match the ForecastTrader
    talk-track narrative.
  * Hide the Kalshi-style CPI tab, Polymarket-style CPI tab, and the
    Index Administrator view (operational tooling, not for external
    reviewers).
  * Block the ?view=index_admin query route.
  * Render a disclaimer footer at the bottom of every page.

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
# Tab keys (must match the keys in app.py's _TAB_META):
#   overview  — new framing tab (review build only)
#   hc        — CareFi Healthcare Trend Index (a.k.a. Medical CPI Tracker)
#   cpi       — Oriel CPI Forward Index (Kalshi-style)              [hidden]
#   fx        — Oriel CPI Forward Index (ForecastEx-style)
#   poly      — Oriel CPI Forward Index (Polymarket-style)          [hidden]
#   perp      — Oriel CPI Basis · Cross-Venue Diagnostics
#   cms       — Oriel Healthcare Reference (CMS, backup)
#   med_basis — ForecastEx Medical Inflation Basis Contract
#   parity    — OTC Parity Validation (backup)
# ─────────────────────────────────────────────────────────────────────────────
REVIEW_HIDDEN_TABS: tuple[str, ...] = ("cpi", "poly")

# Order in which the visible tabs are rendered in the review build.
# Sequence matches the talk track's recommended demo order.
REVIEW_TAB_ORDER: tuple[str, ...] = (
    "overview",
    "fx",
    "perp",
    "hc",
    "med_basis",
    "cms",
    "parity",
)

# Tab labels overridden for the review build (talk-track wording).
# Any key not present here falls back to its production label.
REVIEW_TAB_LABELS: dict[str, str] = {
    "overview":  "Overview",
    "fx":        "ForecastEx CPI Forward Index",
    "perp":      "CPI Basis · Cross-Venue Diagnostics",
    "hc":        "Medical CPI Tracker · Healthcare Reference",
    "med_basis": "ForecastEx Medical Inflation Basis Contract",
    "cms":       "CMS Reference (backup)",
    "parity":    "OTC Parity Validation (backup)",
}
