"""
tabs/overview_tab.py — Opening / framing tab for the ForecastTrader review build.

Renders the 30-45 second narrative anchor described in
``Oriel_ForecastEx_Demo_Tabs_Talk_Track_v2.docx``. Visible only when the
review build flag is on (rendered as the first tab).

Pure presentational — no data dependencies, no engine calls. Uses the
shared design language (oriel-page-head, kpi-strip-wrap / kpi-cell, note-box)
so the tab is visually indistinguishable from the rest of the app.
"""
from __future__ import annotations

import streamlit as st

# ── Color constants (match ui/tokens.py exactly) ─────────────────────────────
# Local references to the design tokens used inside inline styles. Keeping
# them mirrored here means we never drift from the rest of the app.
_TEXT_PRI    = "#E6EDF3"   # ui.tokens.TEXT_PRI
_KICKER_GREY = "#8fa3b8"   # convention used by cms_tab / medical_basis_tab subtitles


def render_overview_tab() -> None:
    """Render the talk-track Overview tab."""

    # ── Page header ──────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class='oriel-page-head'>
          <span class='oriel-page-title'>Oriel CPI Demo &middot; Overview</span>
          <span class='version-chip'>ForecastTrader review build</span>
          <span class='version-chip' style='background:#1b2a3e;color:#7aa2f7;border-color:#2e4a72;'>
            CPI as the on-ramp &middot; Healthcare as the differentiated module
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div style='font-size:0.75rem;color:{_KICKER_GREY};margin:4px 0 8px;'>"
        "Oriel converts discrete CPI event contracts into continuous, "
        "institution-grade macro surfaces. This review build walks through the "
        "CPI workflow first, then introduces the medical-inflation expansion path."
        "</div>",
        unsafe_allow_html=True,
    )

    # ── KPI strip: framing in five cells ────────────────────────────────────
    st.markdown(
        """
        <div class='kpi-strip-wrap' style='margin-bottom:12px'>
          <div class='kpi-strip-ribbon'>FRAMING &middot; Bridge market &middot; Surface translation &middot; Workflow &middot; Expansion</div>
          <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr))'>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Bridge market</div>
              <div class='kpi-value'>CPI</div>
              <div class='kpi-sub'>Listed, benchmarkable, already trading</div>
            </div>
            <div class='kpi-cell'>
              <div class='kpi-micro'>What Oriel adds</div>
              <div class='kpi-value kpi-value--lead'>Curve</div>
              <div class='kpi-sub'>Discrete contracts &rarr; continuous surface</div>
            </div>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Workflow output</div>
              <div class='kpi-value'>Reference + execution</div>
              <div class='kpi-sub'>Fair value, basis, ladder, guardrails</div>
            </div>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Expansion path</div>
              <div class='kpi-value'>Medical CPI</div>
              <div class='kpi-sub'>Differentiated, hedge-less today</div>
            </div>
            <div class='kpi-cell kpi-cell--pub'>
              <div class='kpi-micro'>Audience</div>
              <div class='kpi-value'>ForecastEx / FT</div>
              <div class='kpi-sub'>Reference logic &middot; Market structure</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Two-up: narrative pillars + walkthrough timing ──────────────────────
    left, right = st.columns([1, 1], gap="medium")

    with left:
        st.markdown(
            f"""
            <div class='note-box'>
              <div style='font-size:0.62rem;letter-spacing:0.16em;text-transform:uppercase;color:{_KICKER_GREY};margin-bottom:8px;'>
                Narrative pillars
              </div>
              <div style='margin-bottom:10px;'>
                <b style='color:{_TEXT_PRI};'>1 &middot; Listed CPI contracts can become a curve.</b><br>
                ForecastEx-style binary thresholds, normalized and stitched into a
                forward CPI surface that institutions can reference.
              </div>
              <div style='margin-bottom:10px;'>
                <b style='color:{_TEXT_PRI};'>2 &middot; A curve is only useful if it is benchmarkable.</b><br>
                Cross-venue diagnostics, confidence, liquidity, and quote freshness
                turn the surface into a relative-value workflow.
              </div>
              <div style='margin-bottom:10px;'>
                <b style='color:{_TEXT_PRI};'>3 &middot; The same workflow extends to medical inflation.</b><br>
                Public BLS medical-CPI components anchor a healthcare reference,
                feeding an illustrative ForecastEx-style basis contract.
              </div>
              <div>
                <b style='color:{_TEXT_PRI};'>4 &middot; The first hedge is medical CPI vs CPI.</b><br>
                A spread every payer, provider, employer, and reinsurer already
                lives with &mdash; but cannot currently hedge.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            f"""
            <div class='note-box'>
              <div style='font-size:0.62rem;letter-spacing:0.16em;text-transform:uppercase;color:{_KICKER_GREY};margin-bottom:8px;'>
                5 &ndash; 7 minute walkthrough
              </div>
              <div style='display:grid;grid-template-columns:64px 1fr;gap:6px 14px;font-size:0.74rem;line-height:1.55;align-items:baseline;'>
                <code>0:00</code>
                <span><b style='color:{_TEXT_PRI};'>Overview.</b> Frame CPI as the on-ramp.</span>
                <code>0:45</code>
                <span><b style='color:{_TEXT_PRI};'>ForecastEx CPI Forward Index.</b> Listed contracts &rarr; curve.</span>
                <code>2:00</code>
                <span><b style='color:{_TEXT_PRI};'>CPI Basis &middot; Diagnostics.</b> Fair value, dislocation, calibration.</span>
                <code>3:15</code>
                <span><b style='color:{_TEXT_PRI};'>Medical CPI Tracker.</b> Healthcare-specific reference, BLS-anchored.</span>
                <code>4:30</code>
                <span><b style='color:{_TEXT_PRI};'>Medical Inflation Basis Contract.</b> Spread ladder + settlement example.</span>
                <code>5:45</code>
                <span><b style='color:{_TEXT_PRI};'>Backups.</b> CMS reference and OTC parity validation if asked.</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Audience lens + close/ask preview ───────────────────────────────────
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    a, b = st.columns([1, 1], gap="medium")

    with a:
        st.markdown(
            f"""
            <div class='note-box'>
              <div style='font-size:0.62rem;letter-spacing:0.16em;text-transform:uppercase;color:{_KICKER_GREY};margin-bottom:8px;'>
                Audience lens
              </div>
              <div style='margin-bottom:8px;'>
                <b style='color:{_TEXT_PRI};'>Jose Torres &middot; senior economist, IBKR / ForecastTrader.</b><br>
                Reference logic, BLS definitions, observability, settlement quality,
                economic soundness.
              </div>
              <div>
                <b style='color:{_TEXT_PRI};'>Rob Prior &middot; CEO, ForecastEx.</b><br>
                Market structure, workflow utility, exchange technology, market-maker
                interfaces, institutional adoption.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with b:
        st.markdown(
            f"""
            <div class='note-box'>
              <div style='font-size:0.62rem;letter-spacing:0.16em;text-transform:uppercase;color:{_KICKER_GREY};margin-bottom:8px;'>
                Close &middot; the ask
              </div>
              <div style='margin-bottom:8px;'>
                Can ForecastEx / ForecastTrader become the venue layer powering a
                broader family of institution-grade macro surfaces &mdash; CPI today,
                healthcare next, then weather, rates, and other macro categories?
              </div>
              <div>
                Where would this be most useful inside the ForecastTrader / IBKR
                environment: analytics, education, market-maker tooling, execution
                templates, or product design?
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Footnote ────────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-size:0.68rem;color:{_KICKER_GREY};margin:14px 0 4px;line-height:1.6;'>"
        "All figures, ladders, and contract specifications shown in this review "
        "build are illustrative and use sample or public data. Live venue feeds "
        "and execution rails are not connected."
        "</div>",
        unsafe_allow_html=True,
    )
