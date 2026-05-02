"""
tabs/medical_basis_tab.py — ForecastEx-style medical inflation basis contract UI.

Drop-in Streamlit tab for the illustrative contract:
  Medical CPI YoY - CPI-U YoY > threshold

This intentionally uses sample ladder data until a venue lists the contract or a
live feed is available. All economic calculations live in
analytics.medical_basis_contract.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.medical_basis_contract import (
    DEFAULT_THRESHOLDS_BPS,
    build_basis_curve,
    basis_curve_dataframe,
    contract_spec_dataframe,
    load_sample_medical_basis_contracts,
    settlement_example,
    settle_medical_basis_contract,
)
from ui.charts import _layout as _chart_layout, _xaxis, _yaxis
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import _plotly_desk_table, desk_table_content_height_px
from ui.tokens import (
    BG_APP,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER,
    BORDER_STR,
    DESK_TABLE_HEADER_PX,
    DESK_TABLE_PAD_PX,
    DESK_TABLE_ROW_PX,
    GOLD,
    GRID_SOFT,
    INFO,
    POSITIVE,
    SERIES2,
    TEXT_MUTED,
    TEXT_PRI,
    TEXT_SEC,
    WARNING,
)


@st.cache_data(show_spinner=False, ttl=600)
def _cached_medical_basis_curve():
    ladder = load_sample_medical_basis_contracts()
    return build_basis_curve(ladder)


def _make_ladder_chart(ladder_df: pd.DataFrame, maturity: pd.Timestamp) -> go.Figure:
    g = ladder_df[ladder_df["maturity"] == pd.to_datetime(maturity)].sort_values("threshold_bps")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[f"> {int(x)}" for x in g["threshold_bps"]],
        y=g["yes_price"] * 100,
        marker=dict(color=GOLD, line=dict(color="rgba(255,255,255,0.14)", width=1)),
        name="YES price / implied probability",
        hovertemplate="<b>Spread %{x} bps</b><br>YES price: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(**_chart_layout(
        height=306,
        xaxis=_xaxis(title="Medical CPI - CPI-U threshold (bps)"),
        yaxis=_yaxis(title="YES price / probability", ticksuffix="%", range=[0, 100]),
    ))
    return fig


def _make_distribution_chart(distribution_df: pd.DataFrame, maturity: pd.Timestamp) -> go.Figure:
    g = distribution_df[distribution_df["maturity"] == pd.to_datetime(maturity)].copy()
    y_max = max(50, float((g["probability"] * 100).max()) + 10)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=g["bucket"],
        y=g["probability"] * 100,
        marker=dict(color=SERIES2, line=dict(color="rgba(255,255,255,0.14)", width=1)),
        name="Implied bucket probability",
        hovertemplate="<b>%{x}</b><br>Probability: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(**_chart_layout(
        height=306,
        margin=dict(l=56, r=24, t=28, b=78),
        xaxis=_xaxis(title="Implied spread bucket", tickangle=-20),
        yaxis=_yaxis(title="Probability", ticksuffix="%", range=[0, y_max]),
    ))
    return fig


def _make_basis_curve(curve_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curve_df["maturity"],
        y=curve_df["expected_spread_bps"],
        mode="lines+markers",
        line=dict(color=GOLD, width=2.6),
        marker=dict(size=8, color=GOLD, line=dict(color=BG_APP, width=1.5)),
        name="Expected medical-vs-CPI basis",
        hovertemplate="<b>%{x|%Y}</b><br>Expected spread: %{y:.1f} bps<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=curve_df["maturity"],
        y=curve_df["probability_spread_gt_200"] * 100,
        mode="lines+markers",
        yaxis="y2",
        line=dict(color=SERIES2, width=2, dash="dot"),
        marker=dict(size=6, color=SERIES2),
        name="P(spread > 200 bps)",
        hovertemplate="<b>%{x|%Y}</b><br>P(>200 bps): %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(**_chart_layout(
        height=322,
        xaxis=_xaxis(title="Maturity", tickformat="%Y"),
        yaxis=_yaxis(title="Expected spread (bps)"),
        yaxis2=dict(
            title=dict(text="Probability", font=dict(color=TEXT_SEC, size=11)),
            overlaying="y",
            side="right",
            ticksuffix="%",
            range=[0, 100],
            showgrid=False,
            tickfont=dict(color=TEXT_SEC),
            zeroline=False,
        ),
    ))
    return fig


def _render_contract_cards() -> None:
    """Three reference-leg / contract-event panels using the standard note-box class
    so the gold-accent border and surface gradient match every other tab."""
    st.markdown(
        f"""
        <div style='display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:8px 0 12px;'>
          <div class='note-box'>
            <div style='font-size:0.72rem;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:.08em;font-weight:600;'>1 · Reference Leg</div>
            <div style='font-size:1.04rem;color:{TEXT_PRI};font-weight:700;margin-top:6px;'>BLS CPI-U YoY</div>
            <div style='font-size:0.74rem;color:{TEXT_SEC};margin-top:4px;'>General inflation benchmark and listed-contract starting point.</div>
          </div>
          <div class='note-box'>
            <div style='font-size:0.72rem;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:.08em;font-weight:600;'>2 · Reference Leg</div>
            <div style='font-size:1.04rem;color:{TEXT_PRI};font-weight:700;margin-top:6px;'>BLS Medical Care CPI YoY</div>
            <div style='font-size:0.74rem;color:{TEXT_SEC};margin-top:4px;'>Healthcare-specific inflation anchor for initial contract design.</div>
          </div>
          <div class='note-box'>
            <div style='font-size:0.72rem;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:.08em;font-weight:600;'>3 · Contract Event</div>
            <div style='font-size:1.04rem;color:{TEXT_PRI};font-weight:700;margin-top:6px;'>Medical CPI − CPI-U &gt; threshold</div>
            <div style='font-size:0.74rem;color:{TEXT_SEC};margin-top:4px;'>A YES/NO basis contract that prices healthcare inflation outperformance.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_medical_basis_tab() -> None:
    curve = _cached_medical_basis_curve()
    curve_df = basis_curve_dataframe(curve)
    ladder = curve.ladder

    with st.container(key="medical_basis_ctrl"):
        cl, cr_lbl, cr_dt = st.columns([5, 1, 2], gap="small", vertical_alignment="center", border=False)
        with cl:
            st.markdown(
                """
                <div class='oriel-page-head'>
                  <span class='oriel-page-title'>ForecastEx: Medical Inflation Basis Contract</span>
                  <span class='version-chip'>v0.1.0-medical-basis</span>
                  <span class='version-chip' style='background:#1b2a3e;color:#7aa2f7;border-color:#2e4a72;'>Illustrative contract design</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cr_lbl:
            st.markdown("<div class='ctrl-vd-label'>Valuation Date</div>", unsafe_allow_html=True)
        with cr_dt:
            st.date_input("Valuation Date", value=date.today(), key="vd_medical_basis", label_visibility="collapsed")

    st.markdown(
        "<div style='font-size:0.78rem;color:#8fa3b8;margin:4px 0 8px;'>"
        "First-ever prediction-market contract to price the spread between medical inflation and CPI — "
        "and seed a tradeable healthcare inflation surface.</div>",
        unsafe_allow_html=True,
    )

    _render_contract_cards()

    maturities = list(curve_df["maturity"])
    default_ix = min(1, len(maturities) - 1) if maturities else 0
    # Compact maturity selector — narrow column matching the valuation-date
    # picker pattern used in the rest of the app.
    mat_col, _spacer = st.columns([1, 6], gap="small", vertical_alignment="bottom")
    with mat_col:
        st.markdown("<div class='ctrl-vd-label'>Contract Maturity</div>", unsafe_allow_html=True)
        selected_maturity = st.selectbox(
            "Contract maturity",
            options=maturities,
            index=default_ix,
            format_func=lambda x: pd.to_datetime(x).strftime("%Y"),
            key="medical_basis_maturity",
            label_visibility="collapsed",
        )

    selected_row = curve_df[curve_df["maturity"] == pd.to_datetime(selected_maturity)].iloc[0]

    # ── KPI Trading Strip — matches Healthcare / CPI / Basis tabs ──────────
    obs_window = str(selected_row.observation_window)
    maturity_year = pd.to_datetime(selected_row.maturity).strftime("%Y")
    st.markdown(
        f"""
        <div class='kpi-strip-wrap'>
          <div class='kpi-strip-ribbon'>FORECASTEX MEDICAL BASIS · {obs_window} · Maturity {maturity_year}</div>
          <div class='kpi-strip'>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Expected Basis</div>
              <div class='kpi-value kpi-value--lead'>{selected_row.expected_spread_bps:.1f} bps</div>
              <div class='kpi-sub'>Medical CPI − CPI-U</div>
            </div>
            <div class='kpi-cell'>
              <div class='kpi-micro'>P(spread &gt; 200 bps)</div>
              <div class='kpi-value' style='color:{SERIES2};'>{selected_row.probability_spread_gt_200 * 100:.1f}%</div>
              <div class='kpi-sub'>YES price proxy</div>
            </div>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Settlement Example</div>
              <div class='kpi-value' style='color:{POSITIVE};'>YES / $1.00</div>
              <div class='kpi-sub'>5.6% medical vs. 3.1% CPI</div>
            </div>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Ladder Thresholds</div>
              <div class='kpi-value' style='color:{INFO};'>0–400 bps</div>
              <div class='kpi-sub'>Spread &gt; threshold</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='oriel-section-gap'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.05, 1.35], gap="large", vertical_alignment="top")
    with left:
        st.markdown("<div class='shdr'>Illustrative Contract Spec</div>", unsafe_allow_html=True)
        spec_df = contract_spec_dataframe()
        _spec_row_h = 44
        _spec_content_h  = DESK_TABLE_HEADER_PX + len(spec_df) * _spec_row_h + DESK_TABLE_PAD_PX
        _spec_viewport_h = DESK_TABLE_HEADER_PX + min(len(spec_df), 5) * _spec_row_h + DESK_TABLE_PAD_PX
        spec_fig = _plotly_desk_table(spec_df, row_height=_spec_row_h)
        spec_fig.update_layout(height=_spec_content_h)
        with st.container(height=_spec_viewport_h, border=False, key="scroll_med_basis_spec"):
            st.plotly_chart(spec_fig, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_med_basis_spec")

        st.markdown("<div class='shdr oriel-section-gap'>Objective Settlement Calculator</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            st.markdown("<div class='ctrl-vd-label'>CPI-U YoY (%)</div>", unsafe_allow_html=True)
            cpi_yoy = st.number_input(
                "CPI-U YoY (%)", min_value=-5.0, max_value=20.0, value=3.1, step=0.1,
                key="mb_cpi_yoy", label_visibility="collapsed",
            )
        with c2:
            st.markdown("<div class='ctrl-vd-label'>Medical CPI YoY (%)</div>", unsafe_allow_html=True)
            med_yoy = st.number_input(
                "Medical CPI YoY (%)", min_value=-5.0, max_value=25.0, value=5.6, step=0.1,
                key="mb_med_yoy", label_visibility="collapsed",
            )
        with c3:
            st.markdown("<div class='ctrl-vd-label'>Threshold (bps)</div>", unsafe_allow_html=True)
            threshold = st.selectbox(
                "Threshold (bps)", list(DEFAULT_THRESHOLDS_BPS), index=2,
                key="mb_threshold", label_visibility="collapsed",
            )
        res = settle_medical_basis_contract(cpi_yoy_pct=cpi_yoy, medical_cpi_yoy_pct=med_yoy, threshold_bps=int(threshold))
        outcome_color = POSITIVE if res.settles_yes else WARNING
        st.markdown(
            f"""
            <div class='note-box' style='margin-top:10px;'>
              <div style='font-size:0.72rem;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:.08em;font-weight:600;'>Settlement Output</div>
              <div style='display:flex;justify-content:space-between;margin-top:8px;font-size:0.82rem;'>
                <span style='color:{TEXT_SEC};'>Observed spread</span><span style='color:{TEXT_PRI};font-weight:700;font-variant-numeric:tabular-nums;'>{res.spread_bps:.1f} bps</span>
              </div>
              <div style='display:flex;justify-content:space-between;margin-top:6px;font-size:0.82rem;'>
                <span style='color:{TEXT_SEC};'>Contract threshold</span><span style='color:{TEXT_PRI};font-weight:700;font-variant-numeric:tabular-nums;'>{res.threshold_bps} bps</span>
              </div>
              <div style='display:flex;justify-content:space-between;margin-top:6px;font-size:0.82rem;'>
                <span style='color:{TEXT_SEC};'>Outcome</span><span style='color:{outcome_color};font-weight:800;'>{'YES settles $1.00' if res.settles_yes else 'NO settles $0.00'}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("<div class='shdr'>Contract Ladder & Implied Distribution</div>", unsafe_allow_html=True)
        t1, t2, t3 = st.tabs(["Threshold ladder", "Implied distribution", "Basis curve"])
        with t1:
            st.caption("YES prices approximate market-implied probabilities for each medical-vs-CPI spread threshold.")
            st.plotly_chart(_make_ladder_chart(ladder, selected_maturity), width="stretch", config=PLOTLY_CONFIG, key="chart_med_basis_ladder")
        with t2:
            st.caption("Exceedance prices are converted into a bucketed probability distribution for the spread.")
            st.plotly_chart(_make_distribution_chart(curve.distribution, selected_maturity), width="stretch", config=PLOTLY_CONFIG, key="chart_med_basis_dist")
        with t3:
            st.caption("Expected spread by maturity seeds a market-implied healthcare inflation basis surface.")
            st.plotly_chart(_make_basis_curve(curve_df), width="stretch", config=PLOTLY_CONFIG, key="chart_med_basis_curve")

        st.markdown("<div class='shdr oriel-section-gap'>From Contracts to a Surface</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class='note-box'>
              <div style='display:grid;grid-template-columns:1fr 34px 1fr 34px 1fr;gap:8px;align-items:center;text-align:center;'>
                <div>
                  <div style='font-weight:700;color:{TEXT_PRI};font-size:0.86rem;'>Binary spread contracts</div>
                  <div style='font-size:.72rem;color:{TEXT_MUTED};margin-top:3px;'>YES prices by threshold</div>
                </div>
                <div style='font-size:1.4rem;color:{GOLD};'>→</div>
                <div>
                  <div style='font-weight:700;color:{TEXT_PRI};font-size:0.86rem;'>Oriel reference engine</div>
                  <div style='font-size:.72rem;color:{TEXT_MUTED};margin-top:3px;'>normalize · repair · infer</div>
                </div>
                <div style='font-size:1.4rem;color:{GOLD};'>→</div>
                <div>
                  <div style='font-weight:700;color:{TEXT_PRI};font-size:0.86rem;'>Market-implied basis curve</div>
                  <div style='font-size:.72rem;color:{TEXT_MUTED};margin-top:3px;'>hedges · perps · notes</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Sample contract ladder — gold-accent desk table matching the rest ──
    st.markdown("<div class='shdr oriel-section-gap'>Sample Contract Ladder</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.74rem;color:{TEXT_MUTED};margin:-2px 0 8px;'>"
        f"Illustrative ForecastEx-style ladder — YES prices, bid/ask, volume, open interest by threshold and maturity.</div>",
        unsafe_allow_html=True,
    )
    ladder_table = ladder.copy()
    ladder_table["maturity"] = ladder_table["maturity"].dt.strftime("%Y-%m-%d")
    ladder_table["yes_price"] = (ladder_table["yes_price"] * 100).round(1).astype(str) + "%"
    ladder_table["bid"] = ladder_table["bid"].map(lambda v: f"{v:.2f}")
    ladder_table["ask"] = ladder_table["ask"].map(lambda v: f"{v:.2f}")
    ladder_table["volume"] = ladder_table["volume"].astype(int).map(lambda v: f"{v:,}")
    ladder_table["open_interest"] = ladder_table["open_interest"].astype(int).map(lambda v: f"{v:,}")
    visible_cols = ["maturity", "observation_window", "contract_label", "yes_price", "bid", "ask", "volume", "open_interest", "source_status"]
    ladder_view = ladder_table[visible_cols].rename(columns={
        "maturity":           "Maturity",
        "observation_window": "Observation Window",
        "contract_label":     "Contract",
        "yes_price":          "YES Price",
        "bid":                "Bid",
        "ask":                "Ask",
        "volume":             "Volume",
        "open_interest":      "Open Interest",
        "source_status":      "Status",
    })
    _ladder_h = DESK_TABLE_HEADER_PX + min(len(ladder_view), 8) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    _ladder_content_h = DESK_TABLE_HEADER_PX + len(ladder_view) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    ladder_fig = _plotly_desk_table(ladder_view, gold_column="YES Price")
    ladder_fig.update_layout(height=_ladder_content_h)
    with st.container(height=_ladder_h, border=False, key="scroll_med_basis_ladder"):
        st.plotly_chart(ladder_fig, width="stretch", config=PLOTLY_CONFIG, theme=None, key="tbl_med_basis_ladder")

    if curve.repaired:
        st.warning("One or more ladders required monotonic repair. Check YES prices for arbitrage consistency.")
    else:
        st.markdown(
            f"<div class='note-box' style='margin-top:6px;'>"
            f"<span style='color:{TEXT_SEC};font-size:0.78rem;'>"
            f"<b style='color:{TEXT_PRI};'>Monotonic ✓</b> &nbsp;Sample ladders are arbitrage-consistent: higher thresholds have lower or equal YES prices.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
