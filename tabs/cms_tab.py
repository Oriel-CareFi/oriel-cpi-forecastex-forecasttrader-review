"""
tabs/cms_tab.py — Oriel Healthcare Reference (CMS Lag Engine) tab.

Extracted from app.py lines ~3398-3992.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.tokens import (
    BG_APP, BG_ELEVATED, BG_SURFACE,
    BORDER, BORDER_STR,
    GOLD, GOLD_LIGHT,
    GRID_SOFT,
    POSITIVE, POSITIVE_MUTED, NEGATIVE, WARNING,
    SERIES2, SERIES_MUTE,
    TEXT_PRI, TEXT_SEC, TEXT_MUTED,
    DESK_TABLE_HEADER_PX, DESK_TABLE_ROW_PX, DESK_TABLE_PAD_PX,
    PROJECT_ROOT,
)
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import _plotly_desk_table
from ui.charts import _layout

from analytics.cms_lag_loader import load_pipeline_outputs


_CMS_BUILD_DIR = PROJECT_ROOT / "data" / "cms_lag_engine"


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_cms_outputs():
    return load_pipeline_outputs(_CMS_BUILD_DIR)


def _cms_apply_axis_polish(fig: go.Figure) -> None:
    """Shared x/y axis polish matching v17 other-chart conventions."""
    fig.update_xaxes(tickfont=dict(color=TEXT_PRI, size=11), title_font=dict(color=TEXT_SEC, size=11))
    fig.update_yaxes(title_font=dict(color=TEXT_SEC, size=11))


def _make_cms_hero_chart(anchor_ts: pd.DataFrame, chart_height: int) -> go.Figure:
    fig = go.Figure()
    x = anchor_ts["year"].astype(int)
    rail_vals = anchor_ts["medical_cpi_proxy"].fillna(0).astype(float).tolist()
    spot_vals = anchor_ts["oriel_healthcare_spot"].fillna(0).astype(float).tolist()
    anchor_vals = anchor_ts["cms_official_anchor_yoy"].fillna(0).astype(float).tolist()
    rail_cd = [f"{v:.2f}" for v in rail_vals]
    spot_cd = [f"{v:.2f}" for v in spot_vals]
    anchor_cd = [f"{v:.2f}" for v in anchor_vals]
    fig.add_trace(go.Scatter(
        x=x, y=rail_vals,
        customdata=rail_cd,
        mode="lines+markers", name="Public settlement rail",
        line=dict(color=SERIES2, width=2),
        marker=dict(size=7, color=SERIES2, line=dict(color=BG_SURFACE, width=1.5)),
        hovertemplate="<b>%{x}</b><br>Public rail: %{customdata}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=spot_vals,
        customdata=spot_cd,
        mode="lines+markers", name="Oriel healthcare spot",
        line=dict(color=GOLD, width=2.5),
        marker=dict(size=8, color=GOLD, line=dict(color=BG_SURFACE, width=1.5)),
        hovertemplate="<b>%{x}</b><br>Oriel spot: %{customdata}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=anchor_vals,
        customdata=anchor_cd,
        mode="lines+markers", name="CMS official anchor",
        line=dict(color=GOLD_LIGHT, width=2, dash="dash"),
        marker=dict(size=7, color=GOLD_LIGHT, line=dict(color=BG_SURFACE, width=1.5)),
        hovertemplate="<b>%{x}</b><br>CMS anchor: %{customdata}%<extra></extra>",
    ))
    band = (anchor_ts["public_print_basis_bps"].abs().fillna(0) / 100.0).clip(lower=0.08, upper=0.8)
    upper = anchor_ts["oriel_healthcare_spot"] + band
    lower = anchor_ts["oriel_healthcare_spot"] - band
    fig.add_trace(go.Scatter(
        x=x, y=upper, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=lower, mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(212,168,90,0.10)",
        name="Confidence band", hoverinfo="skip",
    ))
    fig.update_layout(**_layout(
        height=chart_height,
        xaxis_title="Year",
        yaxis_title="YoY (%)",
        showlegend=True,
        title=dict(
            text="Public print \u00b7 Oriel translated spot \u00b7 CMS official anchor (with confidence band)",
            font=dict(size=11, color=TEXT_SEC), x=0.01, xanchor="left", y=0.98, yanchor="top",
        ),
        margin=dict(l=64, r=22, t=52, b=72),
    ))
    fig.update_yaxes(ticksuffix="%", hoverformat=".2f")
    fig.update_xaxes(tickformat="d", hoverformat="d")
    _cms_apply_axis_polish(fig)
    return fig


def _make_cms_basis_chart(anchor_ts: pd.DataFrame, chart_height: int) -> go.Figure:
    fig = go.Figure()
    x = anchor_ts["year"].astype(int)
    _pos_bar = "rgba(34,197,94,0.55)"
    _neg_bar = "rgba(255,107,107,0.60)"
    pub_basis_vals = anchor_ts["public_print_basis_bps"].fillna(0).astype(float).tolist()
    anchor_basis_vals = anchor_ts["anchor_basis_bps"].fillna(0).astype(float).tolist()
    bar_colors = [_pos_bar if v >= 0 else _neg_bar for v in pub_basis_vals]
    bar_line_colors = [POSITIVE_MUTED if v >= 0 else NEGATIVE for v in pub_basis_vals]
    pub_customdata = [f"{v:+.1f}" for v in pub_basis_vals]
    anchor_customdata = [f"{v:+.1f}" for v in anchor_basis_vals]
    fig.add_trace(go.Bar(
        x=x, y=pub_basis_vals,
        customdata=pub_customdata,
        name="Public vs Oriel basis",
        marker=dict(
            color=bar_colors,
            line=dict(color=bar_line_colors, width=1.2),
        ),
        width=0.42,
        hovertemplate="<b>%{x}</b><br>Basis: %{customdata} bp<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=anchor_basis_vals,
        customdata=anchor_customdata,
        mode="lines+markers", name="Oriel vs CMS anchor basis",
        line=dict(color=GOLD, width=2.5),
        marker=dict(size=8, color=GOLD, line=dict(color=BG_SURFACE, width=1.5)),
        hovertemplate="<b>%{x}</b><br>Anchor basis: %{customdata} bp<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=SERIES_MUTE, opacity=0.55, line_width=1)
    fig.update_layout(**_layout(
        height=chart_height,
        xaxis_title="Year",
        yaxis_title="Basis (bp)",
        showlegend=True,
        margin=dict(l=64, r=22, t=22, b=72),
        bargap=0.55,
    ))
    fig.update_yaxes(ticksuffix=" bp", hoverformat="+.1f")
    fig.update_xaxes(tickformat="d", hoverformat="d")
    _cms_apply_axis_polish(fig)
    return fig


def _make_cms_benchmark_chart(benchmark: pd.DataFrame, chart_height: int) -> go.Figure:
    fig = go.Figure()
    x = benchmark["year"].astype(int)
    spot_vals = benchmark["oriel_healthcare_spot"].fillna(0).astype(float).tolist()
    anchor_vals = benchmark["cms_official_anchor_yoy"].fillna(0).astype(float).tolist()
    spot_cd = [f"{v:.2f}" for v in spot_vals]
    anchor_cd = [f"{v:.2f}" for v in anchor_vals]
    fig.add_trace(go.Scatter(
        x=x, y=spot_vals,
        customdata=spot_cd,
        mode="lines+markers", name="Oriel translated signal",
        line=dict(color=GOLD, width=2.5),
        marker=dict(size=8, color=GOLD, line=dict(color=BG_SURFACE, width=1.5)),
        hovertemplate="<b>%{x}</b><br>Oriel spot: %{customdata}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=anchor_vals,
        customdata=anchor_cd,
        mode="lines+markers", name="Later official CMS anchor",
        line=dict(color=SERIES2, width=2, dash="dash"),
        marker=dict(size=7, color=SERIES2, line=dict(color=BG_SURFACE, width=1.5)),
        hovertemplate="<b>%{x}</b><br>CMS anchor: %{customdata}%<extra></extra>",
    ))
    fig.update_layout(**_layout(
        height=chart_height,
        xaxis_title="Year",
        yaxis_title="YoY (%)",
        showlegend=True,
        margin=dict(l=64, r=22, t=22, b=72),
    ))
    fig.update_yaxes(ticksuffix="%", hoverformat=".2f")
    fig.update_xaxes(tickformat="d", hoverformat="d")
    _cms_apply_axis_polish(fig)
    return fig


def _make_cms_error_chart(benchmark: pd.DataFrame, chart_height: int) -> go.Figure:
    fig = go.Figure()
    x = benchmark["year"].astype(int)
    def _err_fill(v):
        av = abs(v)
        if av <= 25:  return "rgba(34,197,94,0.55)"
        if av <= 50:  return "rgba(212,168,90,0.55)"
        return "rgba(255,107,107,0.60)"
    def _err_line(v):
        av = abs(v)
        if av <= 25:  return POSITIVE_MUTED
        if av <= 50:  return GOLD
        return NEGATIVE
    errs = benchmark["prediction_error_bps"].fillna(0).astype(float).tolist()
    fill_colors = [_err_fill(v) for v in errs]
    line_colors = [_err_line(v) for v in errs]
    err_customdata = [f"{v:+.1f}" for v in errs]
    fig.add_trace(go.Bar(
        x=x, y=errs,
        customdata=err_customdata,
        name="Prediction error",
        marker=dict(
            color=fill_colors,
            line=dict(color=line_colors, width=1.2),
        ),
        width=0.42,
        hovertemplate="<b>%{x}</b><br>Error: %{customdata} bp<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=SERIES_MUTE, opacity=0.55, line_width=1)
    fig.update_layout(**_layout(
        height=chart_height,
        xaxis_title="Year",
        yaxis_title="Error (bp)",
        showlegend=False,
        margin=dict(l=64, r=22, t=22, b=72),
        bargap=0.55,
    ))
    fig.update_yaxes(ticksuffix=" bp", hoverformat="+.1f")
    fig.update_xaxes(tickformat="d", hoverformat="d")
    _cms_apply_axis_polish(fig)
    return fig


def render_cms_lag_engine_tab() -> None:
    # ── Load artifacts ───────────────────────────────────────────────────────
    try:
        bundle = _cached_cms_outputs()
    except FileNotFoundError as exc:
        st.error(f"Oriel Healthcare Reference build artifacts missing: {exc}")
        return
    except Exception as exc:
        st.error(f"Oriel Healthcare Reference error: {exc}")
        return

    basis_action = bundle["basis_action_panel"]
    anchor_ts    = bundle["cms_anchor_timeseries"]
    service      = bundle["service_line_signal_panel"]
    benchmark    = bundle["historical_benchmark_panel"]
    manifest     = bundle["provenance_manifest"]

    row = basis_action.iloc[0]
    medical_cpi_pct    = float(row["medical_cpi_proxy"])
    oriel_spot_pct     = float(row["oriel_healthcare_spot"])
    cms_anchor_pct     = float(row["cms_official_anchor_yoy"])
    public_basis_bp    = float(row["public_print_basis_bps"])
    anchor_basis_bp    = float(row["anchor_basis_bps"])
    historical_pct     = float(row["historical_percentile"])
    convergence_window = str(row["expected_convergence_window"])
    confidence_label   = str(row["signal_confidence"])
    trading_lens       = str(row["trading_lens"])
    hedge_lens_text    = str(row["hedge_lens"])

    public_col   = POSITIVE if public_basis_bp >= 0 else NEGATIVE
    anchor_col   = POSITIVE if anchor_basis_bp >= 0 else NEGATIVE
    conf_col     = POSITIVE if confidence_label == "High" else GOLD if confidence_label == "Medium" else NEGATIVE

    # ── Controls row ─────────────────────────────────────────────────────────
    with st.container(key="cms_ctrl"):
        cl, cr = st.columns([4, 2], gap="small", vertical_alignment="center", border=False)
        with cl:
            st.markdown(f"""
            <div class='oriel-page-head'>
              <span class='oriel-page-title'>Oriel Healthcare Reference</span>
              <span class='version-chip'>v0.1.0-phase1</span>
              <span class='version-chip' style='background:#1b2a3e;color:#7aa2f7;border-color:#2e4a72;'>Pipeline-fed \u00b7 Public settlement rail</span>
            </div>""", unsafe_allow_html=True)

    st.markdown(
        "<div style='font-size:0.75rem;color:#8fa3b8;margin:4px 0 8px;'>"
        "Translates public Medical CPI prints into a CMS-anchored healthcare cost view, surfaces the hedgeable basis, "
        "and ranks service-line relative value. The listed rail stays on the clean public print; Oriel's edge is the "
        "translation layer, basis lens, and convergence read.</div>",
        unsafe_allow_html=True,
    )

    # ── Primary KPI strip ────────────────────────────────────────────────────
    _conv_short = convergence_window.replace(" releases", "").replace(" release", "").strip()
    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-bottom:12px'>
      <div class='kpi-strip-ribbon'>ORIEL HEALTHCARE REFERENCE \u00b7 Public rail \u00b7 Translated spot \u00b7 CMS anchor \u00b7 Basis \u00b7 Convergence</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(6,minmax(0,1fr))'>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Medical CPI</div>
          <div class='kpi-value'>{medical_cpi_pct:.2f}%</div>
          <div class='kpi-sub'>BLS public rail</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Oriel Healthcare Spot</div>
          <div class='kpi-value kpi-value--lead'>{oriel_spot_pct:.2f}%</div>
          <div class='kpi-sub'>Translated reference</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>CMS Official Anchor</div>
          <div class='kpi-value'>{cms_anchor_pct:.2f}%</div>
          <div class='kpi-sub'>Latest official print</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Public-Print Basis</div>
          <div class='kpi-value' style='color:{public_col};'>{public_basis_bp:+.1f} bp</div>
          <div class='kpi-sub'>Rail vs Oriel translation</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Expected Convergence</div>
          <div class='kpi-value'>{_conv_short}</div>
          <div class='kpi-sub'>Releases to convergence</div>
        </div>
        <div class='kpi-cell kpi-cell--pub'>
          <div class='kpi-micro'>Signal Confidence</div>
          <div class='kpi-value' style='color:{conf_col};'>{confidence_label}</div>
          <div class='kpi-sub'>{historical_pct:.0f}th historical pct</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Main row: hero chart (left) + basis/action + decomposition (right) ──
    _ip_h = 242
    _dislo_h = 196
    _right_gap = 22
    _right_total = _ip_h + _right_gap + _dislo_h
    _chart_h = _right_total

    left, right = st.columns([2, 1], gap="medium", vertical_alignment="top")

    with left:
        fig_hero = _make_cms_hero_chart(anchor_ts, _chart_h)
        st.plotly_chart(fig_hero, width="stretch", config=PLOTLY_CONFIG, key="cms_hero_chart")

    with right:

        mean_gap_bp = float(service["gap_bps"].mean()) if len(service) else 0.0
        top_sleeve  = str(service.iloc[0]["service_line"]) if len(service) else "n/a"

        st.markdown(f"""
        <div class='ip-wrap'>
          <div class='ip-header'>
            <span class='ip-header-label'>Basis &amp; Action</span>
            <span class='ip-header-status' style='color:{conf_col};'>\u25cf {confidence_label} confidence</span>
          </div>
          <div class='ip-highlight'>
            <span class='ip-hl-label'>Current Translated Basis</span>
            <span class='ip-hl-value' style='color:{anchor_col};'>{anchor_basis_bp:+.1f} bp</span>
          </div>
          <div class='ip-body'>
            <div class='ip-row'><span class='ip-key'>Historical Positioning</span><span class='ip-val'>{historical_pct:.0f}th pct</span></div>
            <div class='ip-row'><span class='ip-key'>Convergence Window</span><span class='ip-val'>{convergence_window}</span></div>
            <div class='ip-row'><span class='ip-key'>Primary Lens</span><span class='ip-val' style='color:{GOLD};'>{trading_lens}</span></div>
            <div class='ip-row'><span class='ip-key'>Public-Print Basis</span><span class='ip-val' style='color:{public_col};'>{public_basis_bp:+.1f} bp</span></div>
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class='dislo-wrap' style='margin-top:8px;'>
          <div class='dislo-header'><span class='dislo-title'>Crosswalk Decomposition</span></div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Avg Service-Line Gap</span>
            <span class='dislo-val' style='color:{POSITIVE if mean_gap_bp >= 0 else NEGATIVE};'>{mean_gap_bp:+.1f} bp</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>Cross-venue avg</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Largest RV Sleeve</span>
            <span class='dislo-val'>{top_sleeve}</span>
            <span class='dislo-signal' style='color:{GOLD};'>Top signal</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Public-Print Basis</span>
            <span class='dislo-val' style='color:{public_col};'>{public_basis_bp:+.1f} bp</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>Rail vs translation</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Signal Confidence</span>
            <span class='dislo-val' style='color:{conf_col};'>{confidence_label}</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>Composite score</span>
          </div>
        </div>""", unsafe_allow_html=True)

    # ── Secondary row: basis history chart (wide) + hedge lens stacked on RV table ──
    st.markdown("<div class='shdr oriel-section-gap'>Basis History \u00b7 Hedge Lens \u00b7 Top RV Sleeves</div>", unsafe_allow_html=True)

    rv = service.copy()
    rv["cms_yoy"]       = rv["cms_yoy"].astype(float).map(lambda v: f"{v:.2f}")
    rv["oriel_signal"]  = rv["oriel_signal"].astype(float).map(lambda v: f"{v:.2f}")
    rv["gap_bps"]       = rv["gap_bps"].astype(float).map(lambda v: f"{v:+.1f}")
    rv["service_line"]  = rv["service_line"].astype(str).str.replace("_", " ").str.title()
    rv_display = rv[["service_line", "cms_yoy", "oriel_signal", "gap_bps", "confidence"]].rename(columns={
        "service_line": "Sleeve",
        "cms_yoy": "CMS YoY (%)",
        "oriel_signal": "Oriel (%)",
        "gap_bps": "Gap (bp)",
        "confidence": "Conf.",
    })
    _rv_h = DESK_TABLE_HEADER_PX + len(rv_display) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    _hedge_h = 188
    _sec_chart_h = _hedge_h + 8 + _rv_h - 16

    sec_l, sec_r = st.columns([2, 1], gap="medium", vertical_alignment="top")

    with sec_l:
        st.markdown('<span class="oriel-main-split-left" aria-hidden="true"></span>', unsafe_allow_html=True)
        fig_basis = _make_cms_basis_chart(anchor_ts, _sec_chart_h)
        st.caption("Public-print basis (bars) and Oriel vs CMS anchor basis (line), year over year.")
        st.plotly_chart(fig_basis, width="stretch", config=PLOTLY_CONFIG, key="cms_basis_chart")

    with sec_r:
        st.markdown('<span class="oriel-main-split-right" aria-hidden="true"></span>', unsafe_allow_html=True)
        residual = public_basis_bp - anchor_basis_bp
        residual_col = POSITIVE if abs(residual) <= 15 else GOLD if abs(residual) <= 30 else NEGATIVE
        st.markdown(f"""
        <div class='dislo-wrap' style='margin-top:0;'>
          <div class='dislo-header'><span class='dislo-title'>Hedge Lens</span></div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Proxy</span>
            <span class='dislo-val'>BLS Medical CPI</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>Public rail</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Hedge Effectiveness</span>
            <span class='dislo-val' style='color:{conf_col};'>{confidence_label}</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>vs translated signal</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Residual Basis Risk</span>
            <span class='dislo-val' style='color:{residual_col};'>{residual:+.1f} bp</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>Service-mix + lag</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Horizon / Phase</span>
            <span class='dislo-val'>Phase 1</span>
            <span class='dislo-signal' style='color:{GOLD};'>Translation layer</span>
          </div>
        </div>""", unsafe_allow_html=True)

        _fig_rv = _plotly_desk_table(rv_display, gold_column="Gap (bp)")
        _fig_rv.update_layout(height=_rv_h)
        st.plotly_chart(_fig_rv, width="stretch", config=PLOTLY_CONFIG, theme=None, key="cms_rv_tbl", height=_rv_h)

    # ── Sub-tabs: Trading / Hedging / Benchmark / Provenance ─────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Strategy Lenses \u00b7 Benchmark \u00b7 Provenance</div>", unsafe_allow_html=True)
    cms_tab_trade, cms_tab_hedge, cms_tab_bench, cms_tab_prov = st.tabs(
        ["Trading", "Hedging", "Benchmark / Validation", "Provenance"]
    )

    with cms_tab_trade:
        st.markdown(f"""
        <div class='kpi-strip-wrap' style='margin-bottom:8px'>
          <div class='kpi-strip-ribbon'>STRATEGY LENSES \u00b7 Three ways to express the Oriel Healthcare Reference signal</div>
          <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(3,minmax(0,1fr))'>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Basis Trade</div>
              <div class='kpi-value' style='font-size:0.92rem;color:{GOLD};'>{trading_lens}</div>
              <div class='kpi-sub'>Public rail vs CMS-anchored translation \u00b7 {convergence_window}</div>
            </div>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Curve / Convergence</div>
              <div class='kpi-value' style='font-size:0.92rem;'>Trade convergence into next prints</div>
              <div class='kpi-sub'>Release-lag vs persistent dislocation \u00b7 1-4 releases</div>
            </div>
            <div class='kpi-cell'>
              <div class='kpi-micro'>Service-Line Dispersion</div>
              <div class='kpi-value' style='font-size:0.92rem;'>Rank sleeves by gap + momentum</div>
              <div class='kpi-sub'>RV baskets and sector sleeves \u00b7 1-3 quarterly reviews</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with cms_tab_hedge:
        hedge_df = pd.DataFrame([
            {
                "Hedge Target": "General healthcare cost inflation",
                "Proxy": "BLS Medical CPI / Oriel reference",
                "Effectiveness": confidence_label,
                "Residual Basis Risk": f"{residual:+.1f} bp",
            },
            {
                "Hedge Target": "Service-line inflation",
                "Proxy": "RV sleeve overlay",
                "Effectiveness": "Medium",
                "Residual Basis Risk": "Service-mix basis",
            },
        ])
        _h_h = DESK_TABLE_HEADER_PX + len(hedge_df) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        _fig_h = _plotly_desk_table(hedge_df, gold_column="Effectiveness")
        _fig_h.update_layout(height=_h_h)
        st.plotly_chart(_fig_h, width="stretch", config=PLOTLY_CONFIG, theme=None, key="cms_hedge_tbl", height=_h_h)
        st.markdown(
            f"<div style='padding:6px 0 2px;font-size:0.68rem;color:{TEXT_MUTED};'>"
            f"Hedge lens is intentionally conservative \u2014 the public rail captures general trend while service-mix and "
            f"annual-lag risk remain after translation. Use Oriel for the basis overlay, not for replacing the rail.</div>",
            unsafe_allow_html=True,
        )

    with cms_tab_bench:
        bench_l, bench_r = st.columns(2, gap="medium")
        with bench_l:
            fig_bench = _make_cms_benchmark_chart(benchmark, 300)
            st.caption("Oriel translated signal vs later official CMS anchor \u2014 historical benchmark.")
            st.plotly_chart(fig_bench, width="stretch", config=PLOTLY_CONFIG, key="cms_bench_chart")
        with bench_r:
            fig_err = _make_cms_error_chart(benchmark, 300)
            st.caption("Prediction error by year (bp). Green \u2264 25 bp, gold 25\u201350 bp, red > 50 bp.")
            st.plotly_chart(fig_err, width="stretch", config=PLOTLY_CONFIG, key="cms_err_chart")

        bench_display = benchmark.copy()
        for col in ["medical_cpi_proxy", "oriel_healthcare_spot", "cms_official_anchor_yoy"]:
            if col in bench_display.columns:
                bench_display[col] = pd.to_numeric(bench_display[col], errors="coerce").map(
                    lambda v: f"{v:.2f}" if pd.notna(v) else ""
                )
        for col in ["prediction_error_bps", "abs_error_bps"]:
            if col in bench_display.columns:
                bench_display[col] = pd.to_numeric(bench_display[col], errors="coerce").map(
                    lambda v: f"{v:+.1f}" if pd.notna(v) else ""
                )
        if "within_25bps" in bench_display.columns:
            bench_display["within_25bps"] = bench_display["within_25bps"].map(
                lambda v: "Yes" if bool(v) else "No"
            )
        bench_display = bench_display.rename(columns={
            "year": "Year",
            "medical_cpi_proxy": "Public Rail (%)",
            "oriel_healthcare_spot": "Oriel Spot (%)",
            "cms_official_anchor_yoy": "CMS Anchor (%)",
            "prediction_error_bps": "Error (bp)",
            "abs_error_bps": "Abs Error (bp)",
            "within_25bps": "Within 25 bp",
        })
        _b_h = DESK_TABLE_HEADER_PX + len(bench_display) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        _fig_b = _plotly_desk_table(bench_display, gold_column="Oriel Spot (%)")
        _fig_b.update_layout(height=_b_h)
        st.plotly_chart(_fig_b, width="stretch", config=PLOTLY_CONFIG, theme=None, key="cms_bench_tbl", height=_b_h)

    with cms_tab_prov:
        parsed_present = manifest.get("parsed_inputs", {}).get("present", [])
        parsed_missing = manifest.get("parsed_inputs", {}).get("missing", [])
        optional_present = manifest.get("parsed_inputs", {}).get("optional_present", [])
        outputs = manifest.get("outputs", {})

        prov_l, prov_r = st.columns([1.3, 1], gap="medium", vertical_alignment="top")

        with prov_l:
            parsed_rows = "".join(
                f"<div class='dislo-row'>"
                f"<span class='dislo-metric' style='font-size:0.72rem;'>{f}</span>"
                f"<span class='dislo-val' style='color:{POSITIVE};'>Present</span>"
                f"<span class='dislo-signal' style='color:{TEXT_MUTED};'>Parsed</span>"
                f"</div>"
                for f in parsed_present
            ) or f"<div class='dislo-row'><span class='dislo-metric' style='color:{TEXT_MUTED};'>None</span><span class='dislo-val'></span><span class='dislo-signal'></span></div>"
            st.markdown(f"""
            <div class='dislo-wrap' style='margin-top:0;'>
              <div class='dislo-header'><span class='dislo-title'>Parsed Inputs ({len(parsed_present)})</span></div>
              {parsed_rows}
            </div>
            """, unsafe_allow_html=True)

            if parsed_missing:
                missing_rows = "".join(
                    f"<div class='dislo-row'>"
                    f"<span class='dislo-metric' style='font-size:0.72rem;'>{f}</span>"
                    f"<span class='dislo-val' style='color:{NEGATIVE};'>Missing</span>"
                    f"<span class='dislo-signal' style='color:{TEXT_MUTED};'>Required</span>"
                    f"</div>"
                    for f in parsed_missing
                )
                st.markdown(f"""
                <div class='dislo-wrap' style='margin-top:8px;'>
                  <div class='dislo-header'><span class='dislo-title'>Missing Inputs ({len(parsed_missing)})</span></div>
                  {missing_rows}
                </div>
                """, unsafe_allow_html=True)

        with prov_r:
            if optional_present:
                optional_rows = "".join(
                    f"<div class='dislo-row'>"
                    f"<span class='dislo-metric' style='font-size:0.72rem;'>{f}</span>"
                    f"<span class='dislo-val' style='color:{GOLD};'>Present</span>"
                    f"<span class='dislo-signal' style='color:{TEXT_MUTED};'>Optional</span>"
                    f"</div>"
                    for f in optional_present
                )
            else:
                optional_rows = f"<div class='dislo-row'><span class='dislo-metric' style='color:{TEXT_MUTED};'>No optional inputs</span><span class='dislo-val'></span><span class='dislo-signal'></span></div>"

            st.markdown(f"""
            <div class='dislo-wrap' style='margin-top:0;'>
              <div class='dislo-header'><span class='dislo-title'>Optional Inputs ({len(optional_present)})</span></div>
              {optional_rows}
            </div>
            """, unsafe_allow_html=True)

            outputs_rows = "".join(
                f"<div class='dislo-row'>"
                f"<span class='dislo-metric' style='font-size:0.72rem;'>{k}</span>"
                f"<span class='dislo-val' style='font-size:0.72rem;'>{v}</span>"
                f"<span class='dislo-signal' style='color:{GOLD};'>Generated</span>"
                f"</div>"
                for k, v in outputs.items()
            ) or f"<div class='dislo-row'><span class='dislo-metric' style='color:{TEXT_MUTED};'>No outputs</span><span class='dislo-val'></span><span class='dislo-signal'></span></div>"
            st.markdown(f"""
            <div class='dislo-wrap' style='margin-top:8px;'>
              <div class='dislo-header'><span class='dislo-title'>Pipeline Outputs ({len(outputs)})</span></div>
              {outputs_rows}
            </div>
            """, unsafe_allow_html=True)

    st.markdown(
        f"<div style='padding:6px 0 2px;font-size:0.68rem;color:{TEXT_MUTED};'>"
        f"Phase 1 only: translated signal, basis lens, RV sleeves, and hedge framing. Phase 2 (dense-grid service-line "
        f"crosswalk, realtime nowcast, claims overlay) not included in this layer.</div>",
        unsafe_allow_html=True,
    )
