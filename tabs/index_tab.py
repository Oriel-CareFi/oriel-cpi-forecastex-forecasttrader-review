"""
tabs/index_tab.py — Healthcare / CPI index tab renderer.

Extracted from app.py lines ~1303-2228.  Contains the live-feed CPI helpers
(load_live_cpi_payload, resolve_cpi_inputs) and the shared render_index()
function used by both the Healthcare and CPI tabs.
"""
from __future__ import annotations

import os
from datetime import date

import pandas as pd
import streamlit as st

from engine import PredictionIndexAdmin
from sample_data import (
    CPI_CONTRACTS_TABLE, CPI_METHODOLOGY, CPI_SNAPSHOTS,
)

from ui.tokens import (
    BG_APP, BG_ELEVATED, BG_SURFACE, BG_SURFACE2,
    BORDER, BORDER_STR,
    GOLD, GOLD_LIGHT,
    GRID_SOFT,
    POSITIVE, POSITIVE_MUTED, NEGATIVE, WARNING, INFO,
    SERIES2, SERIES_MUTE,
    TEXT_PRI, TEXT_SEC, TEXT_MUTED,
    DESK_TABLE_HEADER_PX, DESK_TABLE_ROW_PX, DESK_TABLE_PAD_PX,
    ORIEL_INDEX_TAB_CHART_HEIGHT_PX,
    LIVE_TOGGLE_WIDGET_KEY,
)
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import (
    _plotly_desk_table,
    desk_table_content_height_px,
    desk_table_viewport_height_px,
)
from analytics.medical_cpi_tracker import load_medical_cpi_panel
from tabs.vol_surface_tab import render_vol_surface_engine
from ui.charts import (
    _layout, _xaxis, _yaxis,
    make_forward_curve, make_distribution, _maturity_label,
)

# ── Phase II availability ────────────────────────────────────────────────────
try:
    from venues.kalshi import (
        KalshiAPIError,
        build_live_cpi_feed,
        DEFAULT_CACHE_SECONDS,
        live_feed_runtime_config,
    )
    PHASE2_AVAILABLE = True
except ImportError:
    PHASE2_AVAILABLE = False
    DEFAULT_CACHE_SECONDS = 60
    KalshiAPIError = Exception  # type: ignore[misc,assignment]


def _live_cpi_enabled() -> bool:
    v = os.getenv("KALSHI_ENABLE_LIVE_CPI", "").strip().lower()
    if v in ("1", "true", "yes", "on"):  return True
    if v in ("0", "false", "no", "off"): return False
    try:
        s = st.secrets.get("KALSHI_ENABLE_LIVE_CPI", None)
        if s is not None:
            return str(s).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        pass
    return False


# ── Live feed functions ──────────────────────────────────────────────────────
@st.cache_data(ttl=DEFAULT_CACHE_SECONDS, show_spinner=False)
def load_live_cpi_payload():
    methodology, snapshots, contracts_table, stats = build_live_cpi_feed()
    runtime_meta = {**live_feed_runtime_config(), **stats, "feed_status": "live"}
    return methodology, snapshots, contracts_table, runtime_meta


def resolve_cpi_inputs(use_live: bool):
    if not use_live or not PHASE2_AVAILABLE:
        return CPI_METHODOLOGY, CPI_SNAPSHOTS, CPI_CONTRACTS_TABLE, None
    try:
        return load_live_cpi_payload()
    except KalshiAPIError as exc:
        st.warning(f"Kalshi API unavailable \u2014 using sample data. ({exc})")
        return CPI_METHODOLOGY, CPI_SNAPSHOTS, CPI_CONTRACTS_TABLE, {"feed_status": "unavailable", "error_type": "KalshiAPIError", "detail": str(exc)[:500]}
    except ValueError as exc:
        st.warning(f"Insufficient Kalshi CPI market data \u2014 using sample data. ({exc})")
        return CPI_METHODOLOGY, CPI_SNAPSHOTS, CPI_CONTRACTS_TABLE, {"feed_status": "unavailable", "error_type": "InsufficientData", "detail": str(exc)[:500]}
    except Exception as exc:
        st.warning(f"Live feed error \u2014 using sample data. ({type(exc).__name__}: {exc})")
        return CPI_METHODOLOGY, CPI_SNAPSHOTS, CPI_CONTRACTS_TABLE, {"feed_status": "unavailable", "error_type": type(exc).__name__, "detail": str(exc)[:500]}


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def load_medical_cpi_monitor_payload(prefer_live: bool = True):
    return load_medical_cpi_panel(prefer_live=prefer_live)


def render_medical_cpi_monitor(front_expected_value: float):
    panel = load_medical_cpi_monitor_payload(prefer_live=True)
    latest = panel.latest_table.copy()

    st.markdown("<div class='shdr shdr-major oriel-section-gap'>Medical CPI Monitor</div>", unsafe_allow_html=True)
    blurb_l, blurb_r = st.columns([3, 2], gap="medium", vertical_alignment="center")
    with blurb_l:
        st.markdown(
            f"<div class='note-box'>Official BLS medical-CPI monitor through <b>{panel.as_of_label}</b>. "
            f"Live fetch is attempted first; app falls back to the local seed file when the BLS API is unavailable.</div>",
            unsafe_allow_html=True,
        )
    with blurb_r:
        med_row = latest[latest["component"] == "Medical care"]
        med_yoy = float(med_row["Y/Y (%)"].iloc[0]) if not med_row.empty else float('nan')
        gap_bps = (front_expected_value - med_yoy) * 100.0 if med_row is not None else float('nan')
        st.markdown(
            f"<div class='note-box'><b>Signal vs print</b><br>Oriel front anchor: <b>{front_expected_value:.2f}%</b><br>"
            f"Latest official medical care Y/Y: <b>{med_yoy:.2f}%</b><br>"
            f"Gap: <b>{gap_bps:+.1f} bp</b><br><span style='color:{TEXT_MUTED};'>{panel.source_detail}</span></div>",
            unsafe_allow_html=True,
        )

    breadth = panel.breadth
    _acc = f"{breadth['accelerating_share']:.0f}%" if breadth['accelerating_share'] is not None else "\u2014"
    _wsa = f"{breadth['weighted_share_above_threshold']:.0f}%" if breadth['weighted_share_above_threshold'] is not None else "\u2014"
    _disp = f"{breadth['dispersion_std']:.2f}" if breadth['dispersion_std'] is not None else "\u2014"
    _thr = f"{breadth['threshold_pct']:.0f}" if breadth.get('threshold_pct') is not None else "3"
    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-bottom:10px'>
      <div class='kpi-strip-ribbon'>MEDICAL CPI BREADTH \u00b7 {breadth.get('component_count', 7)} subcomponents</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(3,minmax(0,1fr))'>
        <div class='kpi-cell'><div class='kpi-micro'>Accelerating Share</div>
          <div class='kpi-value kpi-value--lead'>{_acc}</div>
          <div class='kpi-sub'>Y/Y above prior-month Y/Y</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Weighted Share Above {_thr}%</div>
          <div class='kpi-value kpi-value--lead'>{_wsa}</div>
          <div class='kpi-sub'>BLS relative-importance weights</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Cross-Sectional Dispersion</div>
          <div class='kpi-value kpi-value--lead'>{_disp}</div>
          <div class='kpi-sub'>Std dev of Y/Y across components</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    display = latest[["component", "M/M (%)", "Y/Y (%)", "Prev Y/Y", "Weight", "series_id"]].copy()
    display.rename(columns={
        "component": "Component",
        "Weight": "Weight",
        "series_id": "BLS Series",
    }, inplace=True)
    for col in ["M/M (%)", "Y/Y (%)", "Prev Y/Y", "Weight"]:
        display[col] = display[col].map(lambda x: round(float(x), 2) if pd.notna(x) else None)

    tbl_l, hist_r = st.columns([1.9, 1.1], gap="medium", vertical_alignment="top")
    with tbl_l:
        st.markdown("<div class='shdr'>Monthly Medical CPI Tracker</div>", unsafe_allow_html=True)
        tfig = _plotly_desk_table(display, gold_column="Y/Y (%)")
        tfig.update_layout(height=DESK_TABLE_HEADER_PX + 8 * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX)
        st.plotly_chart(tfig, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_medical_cpi_monitor")
    with hist_r:
        st.markdown("<div class='shdr'>Breadth Methodology</div>", unsafe_allow_html=True)
        st.markdown(
            f"""<div class='note-box'>
            <b>Accelerating share</b> = share of tracked medical subcomponents with current Y/Y above prior-month Y/Y.<br><br>
            <b>Weighted share above {breadth['threshold_pct']:.0f}%</b> = share of tracked weights above threshold using BLS relative-importance seed weights.<br><br>
            <b>Dispersion</b> = cross-sectional standard deviation of Y/Y readings across the tracked medical subcomponents.<br><br>
            Components in breadth set: <b>{breadth['component_count']}</b>.
            </div>""",
            unsafe_allow_html=True,
        )


# ── Main render function ─────────────────────────────────────────────────────
def render_index(methodology, snapshots, contracts_table, y_label, unit,
                 desc, steps, tab_key, runtime_meta=None, show_live_toggle=False):

    # Controls row — compact inline at top of tab content
    _live_ok = show_live_toggle and _live_cpi_enabled() and PHASE2_AVAILABLE
    with st.container(key=f"idx_ctrl_{tab_key}"):
        if _live_ok:
            cl, cr_tog, cr_lbl, cr_dt = st.columns([4, 1, 1, 2], gap="small", vertical_alignment="center", border=False)
        else:
            cl, cr_lbl, cr_dt = st.columns([4, 1, 2], gap="small", vertical_alignment="center", border=False)

        with cl:
            st.markdown(f"""
            <div class='oriel-page-head'>
              <span class='oriel-page-title'>{methodology.index_name}</span>
              <span class='version-chip'>v{methodology.methodology_version}</span>
            </div>""", unsafe_allow_html=True)

        with cr_lbl:
            st.markdown("<div class='ctrl-vd-label'>Valuation Date</div>", unsafe_allow_html=True)

        with cr_dt:
            valuation_date = st.date_input(
                "Valuation Date", value=date.today(), key=f"vd_{tab_key}",
                label_visibility="collapsed",
            )

        if _live_ok:
            with cr_tog:
                st.toggle(
                    "Live data",
                    value=True,
                    help=f"Polls Kalshi REST API every {DEFAULT_CACHE_SECONDS}s.",
                    key=LIVE_TOGGLE_WIDGET_KEY,
                )

    # Engine
    admin = PredictionIndexAdmin(methodology=methodology, valuation_date=valuation_date)
    ip = admin.run(snapshots)
    rows = admin.to_dataframe_rows()
    pts = admin.curve()

    front, back = pts[0], pts[-1]
    slope = round(back.expected_value - front.expected_value, 4)
    slope_pct = round((back.expected_value / front.expected_value - 1) * 100, 2) if front.expected_value else 0.0
    flagged = sum(1 for c in contracts_table if c.get("Status") == "Flagged")

    df = pd.DataFrame([{
        "Maturity": r["maturity"],
        "TTM (yrs)": r["ttm_years"],
        f"Expected Value ({unit})": r["expected_value"],
        "Index Level": r["index_level"],
        f"Std Dev ({unit})": r["std_dev"],
        "Source": r["source"],
    } for r in rows])

    # ── KPI Trading Strip ────────────────────────────────────────────────────
    slope_color = f"<span class='{'neg' if slope<0 else 'pos'}'>{slope_pct:+.2f}% term</span>"
    flagged_html = f"<span class='neg'>{flagged} flagged</span>" if flagged else ""
    pub_label = "Eligible" if ip.publishable else "Not eligible"
    pub_cls = "kpi-pub--ok" if ip.publishable else "kpi-pub--no"
    slope_mod = "pos" if slope >= 0 else "neg"

    st.markdown(f"""
    <div class='kpi-strip-wrap'>
      <div class='kpi-strip-ribbon'>{desc}</div>
      <div class='kpi-strip'>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Official Index Print</div>
          <div class='kpi-value'>{ip.index_level:.2f}</div>
          <div class='kpi-sub'>Base {ip.base_value:.0f}</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>FRONT (1M IMPLIED)</div>
          <div class='kpi-value kpi-value--lead'>{front.expected_value:.2f}{unit}</div>
          <div class='kpi-sub'>{front.maturity.strftime("%b %Y")}</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>BACK (6M IMPLIED)</div>
          <div class='kpi-value kpi-value--back'>{back.expected_value:.2f}{unit}</div>
          <div class='kpi-sub'>{back.maturity.strftime("%b %Y")}</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>TERM STRUCTURE</div>
          <div class='kpi-value kpi-slope--{slope_mod}'>{slope:+.4f}{unit}</div>
          <div class='kpi-sub'>{slope_color}</div>
        </div>
        <div class='kpi-cell kpi-cell--pub'>
          <div class='kpi-micro'>Publishability</div>
          <div class='kpi-value kpi-pub-val {pub_cls}'>{pub_label}</div>
          <div class='kpi-sub'>{flagged_html}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Compute chart height to match right panel ────────────────────────────
    # Measured from DOM: IP=318, dislo=179, gap=8 -> right_total=505
    # Left overhead: tab bar(48) + panel padding/margin(30) + Streamlit chart container(+10) = 98
    _ip_h = 318
    _dislo_h = 179
    _right_total = _ip_h + 8 + _dislo_h   # 505
    _left_overhead = 128
    _chart_h = _right_total - _left_overhead  # 377

    # ── Main layout -- 2:1 ───────────────────────────────────────────────────
    left, right = st.columns([2, 1], gap="medium", vertical_alignment="top")

    with left:
        st.markdown(
            '<span class="oriel-main-split-left" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        mats = pd.to_datetime(df["Maturity"])
        evs = df[f"Expected Value ({unit})"].tolist()
        stds = df[f"Std Dev ({unit})"].tolist()
        fig = make_forward_curve(
            mats, evs, stds, y_label, chart_height=_chart_h
        )

        snap = snapshots[0]
        dlabels, dprobs = [], []
        if snap.scalar_buckets:
            total = sum(max(b.price, 0) for b in snap.scalar_buckets) or 1
            dlabels = [b.label for b in snap.scalar_buckets]
            dprobs = [round(max(b.price, 0) / total * 100, 2) for b in snap.scalar_buckets]
        elif snap.binary_thresholds:
            sorted_t = sorted(snap.binary_thresholds, key=lambda t: t.threshold)
            cap, surv = 1.0, []
            for t in sorted_t:
                p = min(max(t.price, 0), cap)
                surv.append((t.threshold, p))
                cap = p
            bp, bl = [], []
            bp.append(max(1.0 - surv[0][1], 0))
            bl.append(f"<{surv[0][0]:.1f}%")
            for i in range(len(surv) - 1):
                k0, s0 = surv[i]
                k1, s1 = surv[i + 1]
                bp.append(max(s0 - s1, 0))
                bl.append(f"{k0:.1f}\u2013{k1:.1f}%")
            bp.append(max(surv[-1][1], 0))
            bl.append(f">{surv[-1][0]:.1f}%")
            total = sum(bp) or 1
            dlabels, dprobs = bl, [round(p / total * 100, 2) for p in bp]
        elif snap.exact_outcomes:
            total = sum(max(o.price, 0) for o in snap.exact_outcomes) or 1
            dlabels = [f"{o.value:.1f}%" for o in snap.exact_outcomes]
            dprobs = [round(max(o.price, 0) / total * 100, 2) for o in snap.exact_outcomes]

        ev_for_vline = front.expected_value if dlabels else None
        dfig = make_distribution(
            dlabels,
            dprobs,
            expected_value=ev_for_vline,
            chart_height=_chart_h,
        )

        tab_curve, tab_front = st.tabs(["Forward curve", "Front maturity"])
        with tab_curve:
            st.caption(f"Term structure of implied {y_label.lower()} across maturities.")
            st.plotly_chart(
                fig,
                width="stretch",
                config=PLOTLY_CONFIG,
                key=f"fwd_curve_{tab_key}",
            )
        with tab_front:
            st.caption(
                f"Probability mix at front anchor ({front.maturity.strftime('%b %Y')})."
            )
            st.plotly_chart(
                dfig,
                width="stretch",
                config=PLOTLY_CONFIG,
                key=f"dist_front_{tab_key}",
            )

    with right:
        st.markdown(
            '<span class="oriel-main-split-right" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        # Index Print
        print_rows = [
            ("Index Name",        methodology.index_name),
            ("Methodology",       f"v{methodology.methodology_version}"),
            ("Valuation Time",    ip.valuation_time.strftime("%Y-%m-%d %H:%M UTC")),
            ("Base Value",        f"{ip.base_value:.2f}"),
            ("Anchor Exp. Value", f"{ip.anchor_expected_value:.4f}{unit}"),
            ("Publishable",       "Yes \u2713" if ip.publishable else "No \u2717"),
            ("Constituents",      str(len(ip.constituents))),
        ]
        rows_html = "".join(
            f"<div class='ip-row'><span class='ip-key'>{k}</span><span class='ip-val'>{v}</span></div>"
            for k,v in print_rows
        )
        st.markdown(f"""
        <div class='ip-wrap'>
          <div class='ip-header'>
            <span class='ip-header-label'>Index Print</span>
            <span class='ip-header-status'>{"● Published" if ip.publishable else "○ Unpublished"}</span>
          </div>
          <div class='ip-highlight'>
            <span class='ip-hl-label'>Base-100 Front Anchor</span>
            <span class='ip-hl-value'>{ip.index_level:.4f}</span>
          </div>
          <div class='ip-body'>{rows_html}</div>
        </div>""", unsafe_allow_html=True)

        # Dislocation panel (title merged into header -- avoids extra shdr gap)
        ev_front = front.expected_value
        cpi_swap_proxy = round(ev_front * 1.018, 4)   # illustrative proxy
        energy_signal  = "\u2191 Elevated"
        dislocation    = round((cpi_swap_proxy - ev_front) * 100, 1)
        dislo_color = POSITIVE if dislocation < 0 else NEGATIVE
        st.markdown(f"""
        <div class='dislo-wrap'>
          <div class='dislo-header'>
            <span class='dislo-title'>Market vs Signal</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Oriel Forward ({front.maturity.strftime("%b")})</span>
            <span class='dislo-val'>{ev_front:.4f}%</span>
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

    # ── Stats + Methodology + Live Feed -- 3-column layout ───────────────────
    all_evs = [p.expected_value for p in pts]
    all_stds = [p.std_dev for p in pts if p.std_dev]
    _avg_std_s = f"{sum(all_stds) / len(all_stds):.4f}{unit}" if all_stds else "\u2014"
    _stat_cards = [
        ("Mean (all maturities)", f"{sum(all_evs)/len(all_evs):.4f}{unit}"),
        ("Avg Std Dev", _avg_std_s),
        ("Constituents", str(len(ip.constituents))),
    ]

    meth_df = pd.DataFrame([
        {"Key": "Price basis", "Value": methodology.price_basis},
        {"Key": "Interpolation", "Value": methodology.interpolation_method},
        {"Key": "Weighting", "Value": methodology.weighting_rule},
        {"Key": "Smoothing", "Value": methodology.smoothing_rule},
        {"Key": "Stale market", "Value": methodology.stale_market_rule},
        {"Key": "Fallback", "Value": methodology.fallback_rule},
    ])
    if runtime_meta:
        meta_df = pd.DataFrame([{"Key": k, "Value": str(v)} for k, v in runtime_meta.items()])
        meta_df = meta_df.reset_index(drop=True)
        _fig_meta = _plotly_desk_table(meta_df)
        _shared_tbl_h = desk_table_content_height_px(len(meth_df)) + 13
        _meth_row_h = max(30, (_shared_tbl_h - DESK_TABLE_HEADER_PX) // len(meth_df))
        _fig_meth = _plotly_desk_table(meth_df, row_height=_meth_row_h)
        _fig_meth.update_layout(height=_shared_tbl_h)
        # _fig_meta intentionally not height-capped -- CSS constrains it and enables scroll
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
            st.plotly_chart(
                _fig_meth,
                width="stretch",
                config=PLOTLY_CONFIG,
                theme=None,
                key=f"tbl_meth_{tab_key}",
                height=_shared_tbl_h,
            )
        with fcol:
            st.markdown("<div class='shdr oriel-section-gap'>Live Feed Status</div>", unsafe_allow_html=True)
            _meta_h = DESK_TABLE_HEADER_PX + 6 * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX + 13
            _fig_meta.update_layout(height=_meta_h)
            st.plotly_chart(
                _fig_meta,
                width="stretch",
                config=PLOTLY_CONFIG,
                theme=None,
                key=f"tbl_meta_{tab_key}",
                height=_meta_h,
            )
    else:
        _shared_tbl_h = desk_table_content_height_px(len(meth_df)) + 13
        _meth_row_h = max(30, (_shared_tbl_h - DESK_TABLE_HEADER_PX) // len(meth_df))
        _fig_meth = _plotly_desk_table(meth_df, row_height=_meth_row_h)
        _fig_meth.update_layout(height=_shared_tbl_h)
        scol, mcol = st.columns([1, 2], gap="medium", vertical_alignment="top")
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
            st.plotly_chart(
                _fig_meth,
                width="stretch",
                config=PLOTLY_CONFIG,
                theme=None,
                key=f"tbl_meth_{tab_key}",
                height=_shared_tbl_h,
            )

    # ── How the Curve Is Built -- full width ─────────────────────────────────
    st.markdown("<div class='shdr shdr-major oriel-section-gap'>How the Curve Is Built</div>", unsafe_allow_html=True)
    step_cards = "".join(
        f"<div class='step-card'>"
        f"<div class='step-head'><span class='step-num'>{i:02d}</span>"
        f"<span class='step-title'>{t}</span></div>"
        f"<div class='step-body'>{b}</div></div>"
        for i,(t,b) in enumerate(steps,1)
    )
    st.markdown(f"<div class='steps-row'>{step_cards}</div>", unsafe_allow_html=True)

    # ── Data Tables -- tabbed ────────────────────────────────────────────────
    st.markdown("<hr class='oriel-hr'>", unsafe_allow_html=True)

    # Pre-compute figures that don't depend on UI checkboxes
    sd_c = f"Std Dev ({unit})"
    ev_c = f"Expected Value ({unit})"
    cdf = pd.DataFrame(contracts_table).reset_index(drop=True)
    _flagged = {i for i, r in cdf.iterrows() if r.get("Status") == "Flagged"}
    _co_h = DESK_TABLE_HEADER_PX + 6 * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    _fig_co = _plotly_desk_table(cdf, flagged_rows=_flagged)
    _fig_co.update_layout(height=_co_h)
    ev_col = f"Exp. Value ({unit})"
    cdf2 = pd.DataFrame([{
        "Maturity": _maturity_label(c.maturity),
        ev_col: float(c.expected_value),
        "Index Level": float(c.index_level),
        "Std Dev": (f"{c.std_dev:.4f}" if c.std_dev is not None else "\u2014"),
        "Source": c.source,
        "Flag": "\u26a0" if c.flagged else "",
    } for c in ip.constituents]).reset_index(drop=True)
    _fig_ic = _plotly_desk_table(cdf2, gold_column=ev_col)

    dtab_curve, dtab_contracts, dtab_constituents = st.tabs(
        ["Curve Table", "Contract Observations", "Index Constituents"]
    )

    _idx_name_slug = methodology.index_name.replace(' ','_').lower()

    with dtab_curve:
        ddf = df.copy()
        # compute sigma hint before rendering so show_idx state can modify ddf
        sigma_row: int | None = None
        _hint_md = ""
        if sd_c in ddf.columns and len(ddf) > 0:
            try:
                sigma_row = int(ddf[sd_c].astype(float).values.argmax())
                mxrow = ddf.loc[ddf[sd_c].astype(float).idxmax()]
                mt = mxrow["Maturity"]
                mlab = mt.strftime("%b %Y") if hasattr(mt, "strftime") else str(mt)
                _hint_md = (f"Highest dispersion (\u03c3): "
                            f"<span class='oriel-hint-mono'>{mlab}</span> \u00b7 {mxrow[sd_c]:.4f}{unit}")
            except (ValueError, TypeError, KeyError):
                pass
        th_l, th_r = st.columns([6, 1], vertical_alignment="top")
        with th_l:
            st.markdown("<div class='shdr'>Implied Values by Maturity</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='oriel-hint'>{_hint_md or '&nbsp;'}</div>", unsafe_allow_html=True)
            show_idx = st.checkbox("Show index levels", value=True, key=f"idx_{tab_key}")
        with th_r:
            st.download_button(
                "\u2193 CSV", data=ddf.to_csv(index=False).encode("utf-8"),
                file_name=f"oriel_{_idx_name_slug}_curve_{valuation_date}.csv",
                mime="text/csv", key=f"csv_curve_{tab_key}", type="tertiary",
            )
        if not show_idx:
            ddf = ddf.drop(columns=["Index Level"])
        ddf = ddf.reset_index(drop=True)
        _fig_curve = _plotly_desk_table(
            ddf,
            gold_column=ev_c if ev_c in ddf.columns else None,
            sigma_highlight_row=sigma_row,
        )
        st.plotly_chart(_fig_curve, width="stretch", config=PLOTLY_CONFIG, theme=None, key=f"tbl_curve_{tab_key}")

    with dtab_contracts:
        ch_l, ch_r = st.columns([6, 1], vertical_alignment="top")
        with ch_l:
            st.markdown("<div class='shdr'>Contract Observations</div>", unsafe_allow_html=True)
            st.markdown("<div class='oriel-hint'>Flagged inputs included but marked for review.</div>", unsafe_allow_html=True)
        with ch_r:
            st.download_button(
                "\u2193 CSV", data=cdf.to_csv(index=False).encode("utf-8"),
                file_name=f"oriel_{_idx_name_slug}_contracts_{valuation_date}.csv",
                mime="text/csv", key=f"csv_contracts_{tab_key}", type="tertiary",
            )
        st.plotly_chart(_fig_co, width="stretch", config=PLOTLY_CONFIG, theme=None, key=f"tbl_contracts_{tab_key}", height=_co_h)

    with dtab_constituents:
        ih_l, ih_r = st.columns([6, 1], vertical_alignment="top")
        with ih_l:
            st.markdown("<div class='shdr'>Index Constituent Detail</div>", unsafe_allow_html=True)
            st.markdown("<div class='oriel-hint'>Constituent-level breakdown as published in the IndexPrint.</div>", unsafe_allow_html=True)
        with ih_r:
            st.download_button(
                "\u2193 CSV", data=cdf2.to_csv(index=False).encode("utf-8"),
                file_name=f"oriel_{_idx_name_slug}_constituents_{valuation_date}.csv",
                mime="text/csv", key=f"csv_constituents_{tab_key}", type="tertiary",
            )
        st.plotly_chart(_fig_ic, width="stretch", config=PLOTLY_CONFIG, theme=None, key=f"tbl_constituents_{tab_key}")

    # ── Notes + Phase II ─────────────────────────────────────────────────────
    st.markdown("<hr class='oriel-hr'>", unsafe_allow_html=True)
    nc, pc = st.columns(2, gap="large", vertical_alignment="top")
    with nc:
        st.markdown("<div class='shdr'>Notes</div>", unsafe_allow_html=True)
        st.markdown("""<div class='note-box'>
            Phase II live Kalshi CPI feed is integrated and ready.
            Set <code>KALSHI_ENABLE_LIVE_CPI=true</code> in <code>.env</code> to activate.<br><br>
            Sample data remains available as fallback when live feed is disabled or unavailable.
            Engine layer unchanged \u2014 live markets map directly into <code>MaturitySnapshot</code> objects.
        </div>""", unsafe_allow_html=True)
    with pc:
        st.markdown("<div class='shdr'>Phase II \u2014 Live Data & Backtest</div>", unsafe_allow_html=True)
        st.markdown("""<div class='p2-wrap'>
          <div class='p2-item'><span>\u2705</span><div><b>Live Kalshi integration</b> \u2014 REST-first polling with <code>st.cache_data</code>, pagination, quote-waterfall pricing, automatic fallback.</div></div>
          <div class='p2-item'><span>\u2705</span><div><b>Governed mapping</b> \u2014 Markets classified into threshold or exact-outcome contracts, normalized into existing engine inputs.</div></div>
          <div class='p2-item'><span>\U0001f680</span><div><b>Enable live feed</b> \u2014 Set <code>KALSHI_ENABLE_LIVE_CPI=true</code> in Streamlit Cloud secrets. See <code>.env</code> for all options.</div></div>
        </div>""", unsafe_allow_html=True)

    if tab_key == "cpi":
        st.markdown(
            "<div class='oriel-kalshi-footer'><strong>Kalshi-facing summary</strong> \u2014 "
            "CPI implied levels follow the methodology table above. With live data enabled, inputs are Kalshi REST quotes "
            "(cached polling); otherwise sample snapshots illustrate the pipeline. For review: confirm feed status, "
            "contract mapping, and publishability in the KPI strip. Not investment advice.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='oriel-kalshi-footer'><strong>CareFi view</strong> \u2014 "
            "Healthcare trend index from scalar bucket prices; methodology version is on the strip above. "
            "Use for internal demonstration of the same engine path as CPI.</div>",
            unsafe_allow_html=True,
        )

    if tab_key == "hc":
        render_medical_cpi_monitor(front.expected_value)

    if tab_key == "cpi":
        render_vol_surface_engine(snapshots, valuation_date)
