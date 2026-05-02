"""
tabs/forecastex_tab.py — ForecastEx venue tab renderer.

Extracted from app.py lines ~2230-2471.
"""
from __future__ import annotations

from datetime import date, datetime, timezone as _tz
_UTC = _tz.utc

import pandas as pd
import streamlit as st

from venues.forecastex import ForecastExClient, DEFAULT_CONFIG as FX_CONFIG, score_and_package as fx_score_and_package

# REVIEW_BUILD = True forces sample-only data in this tab and hides the
# Live-data toggle. Per the ForecastTrader review-build handoff, the
# external app should show sanitized / sample data only — no calls to
# the public ForecastEx pairs feed.
from config.review_build import REVIEW_BUILD

from ui.tokens import (
    BG_APP, BG_ELEVATED, BG_SURFACE,
    BORDER, BORDER_STR,
    GOLD, GOLD_LIGHT,
    GRID_SOFT,
    POSITIVE, POSITIVE_MUTED, NEGATIVE, WARNING,
    SERIES2, SERIES_MUTE,
    TEXT_PRI, TEXT_SEC, TEXT_MUTED,
    DESK_TABLE_HEADER_PX, DESK_TABLE_ROW_PX, DESK_TABLE_PAD_PX,
    FX_LIVE_TOGGLE_KEY,
)
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import (
    _plotly_desk_table,
    desk_table_content_height_px,
)
from ui.charts import make_forward_curve


@st.cache_data(show_spinner=False, ttl=600)
def _cached_forecastex():
    client = ForecastExClient(FX_CONFIG)
    contracts, source_status = client.fetch_contracts()
    return fx_score_and_package(contracts, source_status=source_status, config=FX_CONFIG)


def render_forecastex_tab() -> None:
    # Controls row
    with st.container(key="fx_ctrl"):
        cl, cr_tog, cr_lbl, cr_dt = st.columns([4, 1, 1, 2], gap="small", vertical_alignment="center", border=False)
        with cl:
            st.markdown(f"""
            <div class='oriel-page-head'>
              <span class='oriel-page-title'>Oriel CPI Forward Index</span>
              <span class='version-chip'>v0.3.0-forecastex-live</span>
              <span class='version-chip' style='background:#1b2a3e;color:#7aa2f7;border-color:#2e4a72;'>Venue Input: ForecastEx</span>
            </div>""", unsafe_allow_html=True)
        with cr_tog:
            if REVIEW_BUILD:
                # Force sample-only data for external review. Show a static
                # chip in place of the toggle so reviewers see the data
                # source explicitly.
                st.markdown(
                    "<div style='display:flex;justify-content:center;"
                    "align-items:center;padding:6px 0;'>"
                    "<span class='version-chip'>Sample data</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.toggle(
                    "Live data",
                    value=True,
                    help="Polls ForecastEx pairs feed. Off = sample data.",
                    key=FX_LIVE_TOGGLE_KEY,
                )
        with cr_lbl:
            st.markdown("<div class='ctrl-vd-label'>Valuation Date</div>", unsafe_allow_html=True)
        with cr_dt:
            st.date_input("Valuation Date", value=date.today(), key="vd_fx", label_visibility="collapsed")

    st.markdown(
        "<div style='font-size:0.75rem;color:#8fa3b8;margin:4px 0 8px;'>"
        "US CPI year-over-year, derived from ForecastEx-style CPI forecast contracts "
        "and normalized into a continuous Oriel forward curve.</div>",
        unsafe_allow_html=True,
    )

    # REVIEW_BUILD overrides any session-state toggle and forces sample data,
    # so a returning reviewer can never accidentally activate the live feed.
    _fx_live = (not REVIEW_BUILD) and st.session_state.get(FX_LIVE_TOGGLE_KEY, True)
    try:
        if _fx_live:
            curve = _cached_forecastex()
        else:
            _client = ForecastExClient(FX_CONFIG)
            _sample = _client._sample_contracts(datetime.now(_UTC))
            curve = fx_score_and_package(_sample, source_status="FALLBACK", config=FX_CONFIG)
    except Exception as exc:
        st.error(f"ForecastEx feed error: {exc}")
        return

    if not curve.points:
        st.warning("No eligible ForecastEx CPI contracts were found for the selected valuation timestamp.")
        return

    front = curve.points[0]
    back  = curve.points[min(len(curve.points) - 1, 5)]
    term_structure = round(back.implied_yoy - front.implied_yoy, 4)
    slope_mod  = "pos" if term_structure >= 0 else "neg"
    slope_pct  = round(term_structure * 100, 2)
    pub_label  = "Eligible" if curve.publishable else "Conditional"
    pub_cls    = "kpi-pub--ok" if curve.publishable else "kpi-pub--no"
    flagged_html = "" if curve.publishable else f"<span class='neg'>{curve.publishability_reason}</span>"

    st.markdown(f"""
    <div class='kpi-strip-wrap'>
      <div class='kpi-strip-ribbon'>US CPI YoY \u00b7 ForecastEx-style binary threshold contracts \u00b7 Oriel normalized forward curve</div>
      <div class='kpi-strip'>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Official Index Print</div>
          <div class='kpi-value'>100.00</div>
          <div class='kpi-sub'>Base 100</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>FRONT (1M IMPLIED)</div>
          <div class='kpi-value kpi-value--lead'>{front.implied_yoy:.2f}%</div>
          <div class='kpi-sub'>{front.release_month}</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>BACK (6M IMPLIED)</div>
          <div class='kpi-value kpi-value--back'>{back.implied_yoy:.2f}%</div>
          <div class='kpi-sub'>{back.release_month}</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>TERM STRUCTURE</div>
          <div class='kpi-value kpi-slope--{slope_mod}'>{term_structure:+.4f}%</div>
          <div class='kpi-sub'><span class="{'neg' if term_structure < 0 else 'pos'}">{slope_pct:+.2f}% term</span></div>
        </div>
        <div class='kpi-cell kpi-cell--pub'>
          <div class='kpi-micro'>Publishability</div>
          <div class='kpi-value kpi-pub-val {pub_cls}'>{pub_label}</div>
          <div class='kpi-sub'>{flagged_html}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Chart inputs ─────────────────────────────────────────────────────────
    _mats  = pd.to_datetime([p.release_month + " 1" for p in curve.points])
    _mats_s = pd.Series(_mats)
    _evs  = [p.implied_yoy for p in curve.points]
    _stds = [max(p.upper_band - p.implied_yoy, 0.0001) for p in curve.points]

    _ip_h = 318
    _dislo_h = 179
    _chart_h = (_ip_h + 8 + _dislo_h) - 128

    left, right = st.columns([2, 1], gap="medium", vertical_alignment="top")

    with left:
        st.markdown('<span class="oriel-main-split-left" aria-hidden="true"></span>', unsafe_allow_html=True)
        fig_fwd   = make_forward_curve(_mats_s, _evs, _stds, "Implied CPI YoY (%)", chart_height=_chart_h)
        _mats_f   = pd.Series(_mats[:1])
        fig_front = make_forward_curve(_mats_f, _evs[:1], _stds[:1], "Implied CPI YoY (%)", chart_height=_chart_h)

        tab_fx_curve, tab_fx_front = st.tabs(["Forward curve", "Front maturity"])
        with tab_fx_curve:
            st.caption("Term structure of implied CPI YoY (%) across maturities.")
            st.plotly_chart(fig_fwd, width="stretch", config=PLOTLY_CONFIG, key="fwd_curve_fx")
        with tab_fx_front:
            st.caption(f"Front anchor point ({front.release_month}).")
            st.plotly_chart(fig_front, width="stretch", config=PLOTLY_CONFIG, key="dist_front_fx")

    with right:
        st.markdown('<span class="oriel-main-split-right" aria-hidden="true"></span>', unsafe_allow_html=True)
        cpi_swap_proxy = round(front.implied_yoy * 1.018, 4)
        dislocation    = round((cpi_swap_proxy - front.implied_yoy) * 100, 1)
        dislo_color    = POSITIVE if dislocation < 0 else NEGATIVE
        energy_signal  = "\u2191 Elevated"

        print_rows = [
            ("Index Name",        "Oriel CPI Forward Index"),
            ("Methodology",       curve.methodology),
            ("Venue",             curve.venue),
            ("Valuation Time",    curve.valuation_timestamp.strftime("%Y-%m-%d %H:%M UTC")),
            ("Base Value",        "100.00"),
            ("Anchor Exp. Value", f"{front.implied_yoy:.4f}%"),
            ("Publishable",       "Yes \u2713" if curve.publishable else "Conditional"),
            ("Constituents",      str(len(curve.points))),
        ]
        rows_html = "".join(
            f"<div class='ip-row'><span class='ip-key'>{k}</span><span class='ip-val'>{v}</span></div>"
            for k, v in print_rows
        )
        st.markdown(f"""
        <div class='ip-wrap'>
          <div class='ip-header'>
            <span class='ip-header-label'>Index Print</span>
            <span class='ip-header-status'>{"● Published" if curve.publishable else "○ Unpublished"}</span>
          </div>
          <div class='ip-highlight'>
            <span class='ip-hl-label'>Base-100 Front Anchor</span>
            <span class='ip-hl-value'>100.0000</span>
          </div>
          <div class='ip-body'>{rows_html}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class='dislo-wrap'>
          <div class='dislo-header'><span class='dislo-title'>Market vs Signal</span></div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Oriel Forward ({front.release_month.split()[0]})</span>
            <span class='dislo-val'>{front.implied_yoy:.4f}%</span>
            <span class='dislo-signal' style='color:{GOLD};'>\u2014</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>CPI Swap (proxy)</span>
            <span class='dislo-val'>{cpi_swap_proxy:.4f}%</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>proxy</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Energy Signal</span>
            <span class='dislo-val'>\u2014</span>
            <span class='dislo-signal' style='color:{WARNING};'>{energy_signal}</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Dislocation</span>
            <span class='dislo-val' style='color:{dislo_color};'>{dislocation:+.1f} bp</span>
            <span class='dislo-signal' style='color:{dislo_color};'>{"↑" if dislocation > 0 else "↓"}</span>
          </div>
        </div>""", unsafe_allow_html=True)

    # ── Stats + Methodology + Feed Status ────────────────────────────────────
    _avg_sigma = sum(_stds) / len(_stds)
    _stat_cards = [
        ("Mean (all maturities)", f"{sum(_evs)/len(_evs):.4f}%"),
        ("Avg \u03c3",                 f"{_avg_sigma:.4f}%"),
        ("Constituents",          str(len(curve.points))),
    ]
    meth_df = pd.DataFrame([
        {"Key": "Price basis",   "Value": "forecastex_mid"},
        {"Key": "Normalization", "Value": "coupon-adjusted mid"},
        {"Key": "Interpolation", "Value": "log-linear"},
        {"Key": "Publishability","Value": "volume + OI threshold"},
        {"Key": "Stale rule",    "Value": f"{FX_CONFIG.stale_after_minutes}min timeout"},
        {"Key": "Fallback",      "Value": "sample_data_on_live_failure"},
    ])
    _shared_tbl_h = desk_table_content_height_px(len(meth_df)) + 13
    _meth_row_h   = max(30, (_shared_tbl_h - DESK_TABLE_HEADER_PX) // len(meth_df))
    _fig_meth = _plotly_desk_table(meth_df, row_height=_meth_row_h)
    _fig_meth.update_layout(height=_shared_tbl_h)

    meta_rows = [
        ("series_ticker",    "FXCPI"),
        ("source_status",    curve.source_status),
        ("sample_mode",      str(curve.sample_mode)),
        ("min_volume",       str(FX_CONFIG.min_volume)),
        ("min_open_interest",str(FX_CONFIG.min_open_interest)),
        ("max_curve_points", str(FX_CONFIG.max_curve_points)),
    ]
    meta_df = pd.DataFrame([{"Key": k, "Value": v} for k, v in meta_rows])
    _meta_h = DESK_TABLE_HEADER_PX + 6 * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX + 13
    _fig_meta = _plotly_desk_table(meta_df)
    _fig_meta.update_layout(height=_meta_h)

    scol, mcol, fcol = st.columns([0.65, 1.6, 2.1], gap="medium", vertical_alignment="top")
    with scol:
        st.markdown("<div class='shdr oriel-section-gap'>Index Stats</div>", unsafe_allow_html=True)
        for lbl, val in _stat_cards:
            st.markdown(
                f"<div class='stat-mini'><div class='stat-mini-label'>{lbl}</div>"
                f"<div class='stat-mini-value'>{val}</div></div>",
                unsafe_allow_html=True,
            )
    with mcol:
        st.markdown("<div class='shdr oriel-section-gap'>Methodology</div>", unsafe_allow_html=True)
        st.plotly_chart(_fig_meth, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_meth_fx", height=_shared_tbl_h)
    with fcol:
        st.markdown("<div class='shdr oriel-section-gap'>Live Feed Status</div>", unsafe_allow_html=True)
        st.plotly_chart(_fig_meta, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_meta_fx", height=_meta_h)

    if curve.sample_mode:
        st.warning("ForecastEx live feed unavailable. Falling back to configured sample payload.")
    elif not curve.publishable:
        st.info("ForecastEx live feed is reachable, but not enough CPI maturities passed publishability checks to build a full curve.")
