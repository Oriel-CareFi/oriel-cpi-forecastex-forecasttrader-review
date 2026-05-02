"""
tabs/ — Oriel tab renderer modules.

Each file corresponds to one top-level tab in the Streamlit app.
All render functions are re-exported here so app.py can do:

    from tabs import render_index, render_forecastex_tab, ...
"""
from __future__ import annotations

from tabs.index_tab import load_live_cpi_payload, resolve_cpi_inputs, render_index
from tabs.forecastex_tab import render_forecastex_tab
from tabs.polymarket_tab import render_polymarket_tab
from tabs.perp_readiness_tab import render_perp_readiness_tab
from tabs.cms_tab import render_cms_lag_engine_tab
from tabs.parity_tab import render_parity_tab
from tabs.index_admin_tab import render_index_admin_tab
from tabs.medical_basis_tab import render_medical_basis_tab
from tabs.overview_tab import render_overview_tab

__all__ = [
    "load_live_cpi_payload",
    "resolve_cpi_inputs",
    "render_index",
    "render_forecastex_tab",
    "render_polymarket_tab",
    "render_perp_readiness_tab",
    "render_cms_lag_engine_tab",
    "render_parity_tab",
    "render_index_admin_tab",
    "render_medical_basis_tab",
    "render_overview_tab",
]
