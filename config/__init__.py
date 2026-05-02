"""
config/ — Build-time and deployment-specific configuration.

Modules in this package are read by app.py and tab renderers to alter
behavior between the production deployment and the ForecastTrader
external-review build, without changing any tab logic.
"""
from __future__ import annotations

from config.review_build import (
    REVIEW_BUILD,
    REVIEW_AUDIENCE,
    REVIEW_APP_LABEL,
    REVIEW_FOOTER,
    REVIEW_HIDDEN_TABS,
    REVIEW_TAB_ORDER,
    REVIEW_TAB_LABELS,
)

__all__ = [
    "REVIEW_BUILD",
    "REVIEW_AUDIENCE",
    "REVIEW_APP_LABEL",
    "REVIEW_FOOTER",
    "REVIEW_HIDDEN_TABS",
    "REVIEW_TAB_ORDER",
    "REVIEW_TAB_LABELS",
]
