"""
tabs/polymarket_tab.py — Polymarket venue tab renderer.

Extracted from app.py lines ~2239-2242 + 2515-2821.
"""
from __future__ import annotations

from datetime import date, datetime, timezone as _tz
_UTC = _tz.utc

import pandas as pd
import streamlit as st

from venues.polymarket import PolymarketClient, DEFAULT_CONFIG as POLY_CONFIG, score_and_package as poly_score_and_package

from ui.tokens import (
    BG_APP, BG_ELEVATED, BG_SURFACE,
    BORDER, BORDER_STR,
    GOLD, GOLD_LIGHT,
    GRID_SOFT,
    POSITIVE, POSITIVE_MUTED, NEGATIVE, WARNING,
    SERIES2, SERIES_MUTE,
    TEXT_PRI, TEXT_SEC, TEXT_MUTED,
    DESK_TABLE_HEADER_PX, DESK_TABLE_ROW_PX, DESK_TABLE_PAD_PX,
    POLY_LIVE_TOGGLE_KEY,
)
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import (
    _plotly_desk_table,
    desk_table_content_height_px,
)
from ui.charts import make_forward_curve


@st.cache_data(show_spinner=False, ttl=600)
def _cached_polymarket():
    client = PolymarketClient(POLY_CONFIG)
    contracts, source_status = client.fetch_contracts()
    return poly_score_and_package(contracts, source_status=source_status, config=POLY_CONFIG)


def render_polymarket_tab() -> None:
    with st.container(key="poly_ctrl"):
        cl, cr_tog, cr_lbl, cr_dt = st.columns([4, 1, 1, 2], gap="small", vertical_alignment="center", border=False)
        with cl:
            st.markdown(f"""
            <div class='oriel-page-head'>
              <span class='oriel-page-title'>Oriel CPI Forward Index</span>
              <span class='version-chip'>v0.1.0-polymarket-live</span>
              <span class='version-chip' style='background:#1b2a3e;color:#7ee0c5;border-color:#1f6b61;'>Venue Input: Polymarket</span>
            </div>""", unsafe_allow_html=True)
        with cr_tog:
            st.toggle(
                "Live data",
                value=True,
                help="Polls public Polymarket market data. Off = sample data.",
                key=POLY_LIVE_TOGGLE_KEY,
            )
        with cr_lbl:
            st.markdown("<div class='ctrl-vd-label'>Valuation Date</div>", unsafe_allow_html=True)
        with cr_dt:
            st.date_input("Valuation Date", value=date.today(), key="vd_poly", label_visibility="collapsed")

    st.markdown(
        "<div style='font-size:0.75rem;color:#8fa3b8;margin:4px 0 8px;'>"
        "US CPI year-over-year, derived from Polymarket CPI threshold contracts and normalized into a continuous Oriel forward curve."
        "</div>",
        unsafe_allow_html=True,
    )

    _poly_live = st.session_state.get(POLY_LIVE_TOGGLE_KEY, True)
    try:
        if _poly_live:
            curve = _cached_polymarket()
        else:
            _client = PolymarketClient(POLY_CONFIG)
            contracts = _client._sample_contracts(datetime.now(_UTC))
            curve = poly_score_and_package(contracts, source_status="FALLBACK", config=POLY_CONFIG)
    except Exception as exc:
        st.error(f"Polymarket feed error: {exc}")
        return

    if not curve.points:
        st.warning("No eligible Polymarket CPI contracts were found for the selected valuation timestamp.")
        return

    front = curve.points[0]
    back  = curve.points[min(len(curve.points) - 1, 5)]
    term_structure = round(back.implied_yoy - front.implied_yoy, 4)
    slope_mod = "pos" if term_structure >= 0 else "neg"
    slope_pct = round(term_structure * 100, 2)
    pub_label = "Eligible" if curve.publishable else "Diagnostic"
    pub_cls   = "kpi-pub--ok" if curve.publishable else "kpi-pub--no"
    flagged_html = "" if curve.publishable else f"<span class='neg'>{curve.publishability_reason}</span>"
    avg_conf = sum(p.confidence_score for p in curve.points) / max(len(curve.points), 1)

    st.markdown(f"""
    <div class='kpi-strip-wrap'>
      <div class='kpi-strip-ribbon'>US CPI YoY \u00b7 Polymarket CPI threshold contracts \u00b7 Oriel normalized forward curve</div>
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
        fig_fwd = make_forward_curve(_mats_s, _evs, _stds, "Implied CPI YoY (%)", chart_height=_chart_h)
        _mats_f = pd.Series(_mats[:1])
        fig_front = make_forward_curve(_mats_f, _evs[:1], _stds[:1], "Implied CPI YoY (%)", chart_height=_chart_h)
        tab_curve, tab_front = st.tabs(["Forward curve", "Front maturity"])
        with tab_curve:
            st.caption("Term structure of implied CPI YoY (%) across maturities.")
            st.plotly_chart(fig_fwd, width="stretch", config=PLOTLY_CONFIG, key="fwd_curve_poly")
        with tab_front:
            st.caption(f"Front anchor point ({front.release_month}).")
            st.plotly_chart(fig_front, width="stretch", config=PLOTLY_CONFIG, key="dist_front_poly")

    with right:
        st.markdown('<span class="oriel-main-split-right" aria-hidden="true"></span>', unsafe_allow_html=True)
        cpi_swap_proxy = round(front.implied_yoy * 1.012, 4)
        dislocation = round((cpi_swap_proxy - front.implied_yoy) * 100, 1)
        dislo_color = POSITIVE if dislocation < 0 else NEGATIVE
        spread_proxy = next((p.spread_bp for p in curve.points if p.spread_bp is not None), 0.0)
        print_rows = [
            ("Index Name",        "Oriel CPI Forward Index"),
            ("Methodology",       curve.methodology),
            ("Venue",             curve.venue),
            ("Venue Role",        curve.venue_role),
            ("Valuation Time",    curve.valuation_timestamp.strftime("%Y-%m-%d %H:%M UTC")),
            ("Base Value",        "100.00"),
            ("Anchor Exp. Value", f"{front.implied_yoy:.4f}%"),
            ("Venue Status",      curve.venue_status.title()),
            ("Reference Status",  "Eligible" if curve.reference_status == "eligible" else "Not eligible for Oriel publication"),
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
            <span class='ip-header-status'>{"● Published" if curve.publishable else "○ Diagnostic"}</span>
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
            <span class='dislo-metric'>Avg spread</span>
            <span class='dislo-val'>{spread_proxy:.1f} bp</span>
            <span class='dislo-signal' style='color:{WARNING};'>venue</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Dislocation</span>
            <span class='dislo-val' style='color:{dislo_color};'>{dislocation:+.1f} bp</span>
            <span class='dislo-signal' style='color:{dislo_color};'>{"↑" if dislocation > 0 else "↓"}</span>
          </div>
        </div>""", unsafe_allow_html=True)

    _avg_sigma = sum(_stds) / len(_stds)
    _stat_cards = [
        ("Mean (all maturities)", f"{sum(_evs)/len(_evs):.4f}%"),
        ("Avg \u03c3",            f"{_avg_sigma:.4f}%"),
        ("Avg confidence",        f"{avg_conf:.1f}"),
    ]
    meth_df = pd.DataFrame([
        {"Key": "Price basis",    "Value": "gamma best bid/ask midpoint"},
        {"Key": "Normalization",  "Value": "threshold midpoint anchored"},
        {"Key": "Interpolation",  "Value": "log-linear"},
        {"Key": "Publishability", "Value": "spread + volume + OI + stale rule"},
        {"Key": "Stale rule",     "Value": f"{POLY_CONFIG.stale_after_hours}h timeout"},
        {"Key": "Fallback",       "Value": "sample_data_on_live_failure"},
    ])
    _shared_tbl_h = desk_table_content_height_px(len(meth_df)) + 13
    _meth_row_h = max(30, (_shared_tbl_h - DESK_TABLE_HEADER_PX) // len(meth_df))
    _fig_meth = _plotly_desk_table(meth_df, row_height=_meth_row_h)
    _fig_meth.update_layout(height=_shared_tbl_h)

    meta_rows = [
        ("source_status", curve.source_status),
        ("sample_mode", str(curve.sample_mode)),
        ("min_volume", str(POLY_CONFIG.min_volume)),
        ("min_open_interest", str(POLY_CONFIG.min_open_interest)),
        ("max_curve_points", str(POLY_CONFIG.max_curve_points)),
        ("websocket_ready", "market-channel compatible"),
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
                f"<div class='stat-mini'><div class='stat-mini-label'>{lbl}</div><div class='stat-mini-value'>{val}</div></div>",
                unsafe_allow_html=True,
            )
    with mcol:
        st.markdown("<div class='shdr oriel-section-gap'>Methodology</div>", unsafe_allow_html=True)
        st.plotly_chart(_fig_meth, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_meth_poly", height=_shared_tbl_h)
    with fcol:
        st.markdown("<div class='shdr oriel-section-gap'>Live Feed Status</div>", unsafe_allow_html=True)
        st.plotly_chart(_fig_meta, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_meta_poly", height=_meta_h)

    cdf = pd.DataFrame([
        {
            "Release": c.release_month,
            "Threshold": (f"{c.threshold:.2f}%" if c.threshold is not None else "\u2014"),
            "Implied CPI": (f"{(c.expected_value or 0):.4f}%" if c.expected_value is not None else "\u2014"),
            "Bid": c.bid if c.bid is not None else "\u2014",
            "Ask": c.ask if c.ask is not None else "\u2014",
            "Spread (bp)": (round((c.spread or 0.0) * 10000.0, 1) if c.spread is not None else "\u2014"),
            "Volume": c.volume if c.volume is not None else "\u2014",
            "OI": c.open_interest if c.open_interest is not None else "\u2014",
            "Confidence": c.confidence_score,
            "Status": "Eligible" if c.publishable else "Flagged",
        }
        for c in curve.contracts
    ]).reset_index(drop=True)
    flagged = {i for i, r in cdf.iterrows() if r.get("Status") == "Flagged"}
    _fig_obs = _plotly_desk_table(cdf, flagged_rows=flagged)
    _fig_obs.update_layout(height=DESK_TABLE_HEADER_PX + min(max(len(cdf), 4), 8) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX + 13)

    cdf2 = pd.DataFrame([
        {
            "Maturity": p.release_month,
            "Exp. Value (%)": p.implied_yoy,
            "Index Level": round(100.0 * (p.implied_yoy / front.implied_yoy), 4) if front.implied_yoy else 100.0,
            "Spread (bp)": p.spread_bp if p.spread_bp is not None else "\u2014",
            "Confidence": p.confidence_score,
            "Market ID": p.market_id,
        }
        for p in curve.points
    ]).reset_index(drop=True)
    _fig_const = _plotly_desk_table(cdf2, gold_column="Exp. Value (%)")
    _fig_const.update_layout(height=DESK_TABLE_HEADER_PX + min(max(len(cdf2), 4), 8) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX + 13)

    dtab_curve, dtab_contracts, dtab_constituents = st.tabs(["Curve Table", "Contract Observations", "Index Constituents"])
    with dtab_curve:
        ddf = pd.DataFrame({
            "Maturity": [p.release_month for p in curve.points],
            "Exp. Value (%)": [p.implied_yoy for p in curve.points],
            "Std Dev": [round(max(p.upper_band - p.implied_yoy, 0.0001), 4) for p in curve.points],
            "Index Level": [round(100.0 * (p.implied_yoy / front.implied_yoy), 4) if front.implied_yoy else 100.0 for p in curve.points],
            "Confidence": [p.confidence_score for p in curve.points],
        })
        th_l, th_r = st.columns([6, 1], vertical_alignment="top")
        with th_l:
            st.markdown("<div class='shdr'>Implied Values by Maturity</div>", unsafe_allow_html=True)
            st.markdown("<div class='oriel-hint'>Polymarket venue-only curve, before any Oriel blend weighting.</div>", unsafe_allow_html=True)
        with th_r:
            st.download_button("\u2193 CSV", data=ddf.to_csv(index=False).encode("utf-8"), file_name=f"oriel_cpi_polymarket_curve_{date.today()}.csv", mime="text/csv", key="csv_curve_poly", type="tertiary")
        _fig_curve = _plotly_desk_table(ddf, gold_column="Exp. Value (%)")
        st.plotly_chart(_fig_curve, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_curve_poly")
    with dtab_contracts:
        ch_l, ch_r = st.columns([6, 1], vertical_alignment="top")
        with ch_l:
            st.markdown("<div class='shdr'>Contract Observations</div>", unsafe_allow_html=True)
            st.markdown("<div class='oriel-hint'>Flagged inputs included but marked for review before contributing to any blend.</div>", unsafe_allow_html=True)
        with ch_r:
            st.download_button("\u2193 CSV", data=cdf.to_csv(index=False).encode("utf-8"), file_name=f"oriel_cpi_polymarket_contracts_{date.today()}.csv", mime="text/csv", key="csv_contracts_poly", type="tertiary")
        st.plotly_chart(_fig_obs, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_contracts_poly")
    with dtab_constituents:
        ih_l, ih_r = st.columns([6, 1], vertical_alignment="top")
        with ih_l:
            st.markdown("<div class='shdr'>Index Constituent Detail</div>", unsafe_allow_html=True)
            st.markdown("<div class='oriel-hint'>One venue-eligible Polymarket market per maturity, chosen by highest confidence.</div>", unsafe_allow_html=True)
        with ih_r:
            st.download_button("\u2193 CSV", data=cdf2.to_csv(index=False).encode("utf-8"), file_name=f"oriel_cpi_polymarket_constituents_{date.today()}.csv", mime="text/csv", key="csv_constituents_poly", type="tertiary")
        st.plotly_chart(_fig_const, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_constituents_poly")

    st.markdown("<hr class='oriel-hr'>", unsafe_allow_html=True)
    nc, pc = st.columns(2, gap="large", vertical_alignment="top")
    with nc:
        st.markdown("<div class='shdr'>Notes</div>", unsafe_allow_html=True)
        st.markdown("""<div class='note-box'>
            Public Polymarket market discovery is integrated via REST polling.
            The handoff is structured so the developer can optionally upgrade this to the public market websocket later without changing the curve packaging layer.<br><br>
            Sample data remains available as fallback when live feed is disabled or unavailable.
            Venue outputs are diagnostic until explicitly blended into the official Oriel CPI basis layer.
        </div>""", unsafe_allow_html=True)
    with pc:
        st.markdown("<div class='shdr'>Phase II \u2014 Live Data & Backtest</div>", unsafe_allow_html=True)
        st.markdown("""<div class='p2-wrap'>
          <div class='p2-item'><span>\u2705</span><div><b>Live Polymarket integration</b> \u2014 public market polling, best bid/ask midpoint normalization, maturity extraction, and controlled CPI filtering.</div></div>
          <div class='p2-item'><span>\u2705</span><div><b>Governed mapping</b> \u2014 threshold markets map into one implied CPI observation per maturity, with confidence scoring and publishability filters.</div></div>
          <div class='p2-item'><span>\U0001f680</span><div><b>Next step</b> \u2014 wire public websocket updates into the same packaging layer for lower-latency venue refreshes.</div></div>
        </div>""", unsafe_allow_html=True)

    if curve.sample_mode:
        st.warning("Polymarket live feed unavailable. Falling back to configured sample payload.")
    elif not curve.publishable:
        st.info("Polymarket live feed is reachable, but not enough CPI maturities passed publishability checks to build a full curve.")
