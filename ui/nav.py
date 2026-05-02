"""
ui/nav.py — Navigation bar rendering, logo, and badge helpers.
"""
from __future__ import annotations

import base64
from datetime import datetime

import streamlit as st

from ui.tokens import PROJECT_ROOT, POSITIVE, WARNING, GOLD, TEXT_MUTED, BORDER_STR


def _logo_data_uri() -> str:
    p = PROJECT_ROOT / "assets" / "oriel_logo.png"
    if p.exists():
        return f"data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"
    return ""


LOGO_DATA_URI = _logo_data_uri()


def render_nav_bar(
    cpi_runtime_meta: dict | None,
    use_live_cpi: bool,
    live_cpi_enabled: bool,
    phase2_available: bool,
    active_view: str = 'main',
    show_index_admin_link: bool = True,
    review_label: str | None = None,
) -> None:
    """Render the top navigation bar.

    Parameters
    ----------
    show_index_admin_link
        If False, the Index Administrator link is hidden. Used by the
        ForecastTrader review build to keep operational tooling out of
        sight for external reviewers.
    review_label
        If set, replaces the Index Administrator link with a non-clickable
        review-build label (e.g. "ForecastTrader review build").
    """
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")

    # CPI badge
    if live_cpi_enabled and phase2_available:
        if cpi_runtime_meta and cpi_runtime_meta.get("feed_status") == "live":
            cpi_nav_badge = f"<span class='nav-badge nav-badge-live'>CPI \u00b7 Live</span>"
        elif use_live_cpi and cpi_runtime_meta and cpi_runtime_meta.get("feed_status") == "unavailable":
            cpi_nav_badge = f"<span class='nav-badge nav-badge-warn'>CPI \u00b7 Offline</span>"
        else:
            cpi_nav_badge = f"<span class='nav-badge nav-badge-mute'>CPI \u00b7 Sample</span>"
    elif live_cpi_enabled:
        cpi_nav_badge = f"<span class='nav-badge nav-badge-warn'>CPI \u00b7 Phase II unavailable</span>"
    else:
        cpi_nav_badge = ""

    feed_live = bool(cpi_runtime_meta and cpi_runtime_meta.get("feed_status") == "live")
    demo_badge = "" if feed_live else "<span class='nav-pill'>\u25c8 Demo</span>"

    # \u2500\u2500 Left-side link / label slot \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if show_index_admin_link:
        active_cls = " nav-label-active" if active_view == 'index_admin' else ""
        left_slot = (
            f"<div class='nav-pipe'></div>"
            f"<a class='nav-label nav-link{active_cls}' href='?view=index_admin' target='_self'>"
            f"Index Administrator</a>"
        )
    elif review_label:
        left_slot = (
            f"<div class='nav-pipe'></div>"
            f"<span class='nav-label' style='color:#d4a85a;letter-spacing:0.04em;'>"
            f"{review_label}</span>"
        )
    else:
        left_slot = ""

    st.markdown(f"""
    <div class='oriel-nav'>
      <div class='nav-left'>
        <a class='nav-home-link' href='?view=main' target='_self' aria-label='Open Oriel home'><img src='{LOGO_DATA_URI}' class='oriel-logo' alt='Oriel'></a>
        {left_slot}
      </div>
      <div class='nav-right'>
        <span class='nav-clock'><span class='nav-time-dot'></span>{now_str} UTC</span>
        {cpi_nav_badge}
        {demo_badge}
      </div>
    </div>
    """, unsafe_allow_html=True)
