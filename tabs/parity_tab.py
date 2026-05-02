"""
tabs/parity_tab.py — OTC Parity Validation tab + DTCC Term Calibration.

Extracted from app.py lines ~3994-4522.
"""
from __future__ import annotations

from pathlib import Path

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
    ORIEL_INDEX_TAB_CHART_HEIGHT_PX,
    PROJECT_ROOT,
)
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import _plotly_desk_table
from ui.charts import _layout, _xaxis, _yaxis

from parity import (
    run_parity,
    ORIEL_CURVE_PATH, TIGHTER_BENCHMARK_PATH,
    DTCC_BENCHMARK_PATH, NEGATIVE_CONTROL_PATH, OUTPUT_DIR,
)
from analytics.dtcc_term_calibration import (
    load_term_calibration as _load_term_calibration,
    filter_standard_tenors as _filter_standard_tenors,
    STANDARD_TENORS as _STANDARD_TENORS,
)

# Module-level flags (these always succeed since the imports above are unconditional;
# the __init__.py guard keeps tabs/ from being imported unless parity/ + analytics/ exist.)
PARITY_AVAILABLE = True
TERM_CALIBRATION_AVAILABLE = True

_TERM_CALIB_DIR = PROJECT_ROOT / "data" / "dtcc_term_calibration"


@st.cache_data(show_spinner=False)
def _cached_parity(oriel_path: str, benchmark_path: str, is_dtcc: bool):
    return run_parity(oriel_path, benchmark_path, is_dtcc, output_dir=OUTPUT_DIR)


def _render_parity_body(bmark_path: str, is_dtcc: bool, key_suffix: str) -> None:
    """Renders KPI strip + charts row + gate/detail columns for one benchmark."""
    try:
        parity_df, summary, grid_df = _cached_parity(str(ORIEL_CURVE_PATH), bmark_path, is_dtcc)
    except Exception as exc:
        st.error(f"Parity pipeline error: {exc}")
        return

    # ── KPI strip ────────────────────────────────────────────────────────────
    ok     = summary["overall_status"] == "PASS"
    thr    = summary["thresholds"]
    shape  = summary.get("shape_metrics", {})
    rate_r2_str      = "n/a" if summary["r_squared"] is None else f"{summary['r_squared']:.4f}"
    index_pillar_str = "n/a" if shape.get("pillar_r2_index") is None else f"{shape['pillar_r2_index']:.4f}"
    index_curve_str  = "n/a" if shape.get("curve_r2_index")  is None else f"{shape['curve_r2_index']:.4f}"
    status_color = POSITIVE if ok else NEGATIVE
    avg_col  = POSITIVE if summary["conditions"]["avg_abs_basis_within_limit"]      else NEGATIVE
    max_col  = POSITIVE if summary["conditions"]["max_abs_basis_within_limit"]      else NEGATIVE
    pct_col  = POSITIVE if summary["conditions"]["pct_within_tolerance_sufficient"] else NEGATIVE
    idx_p_col = POSITIVE if summary["conditions"]["pillar_index_r2_sufficient"]     else WARNING
    idx_c_col = POSITIVE if summary["conditions"]["curve_index_r2_sufficient"]      else WARNING

    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-bottom:14px'>
      <div class='kpi-strip-ribbon'>OTC PARITY STATUS \u00b7 Basis gate + index-space R\u00b2 shape gate \u00b7 ORIEL vs OTC benchmark</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(7,minmax(0,1fr))'>
        <div class='kpi-cell kpi-cell--pub'>
          <div class='kpi-micro'>Overall Status</div>
          <div class='kpi-value' style='color:{status_color};font-size:1.3rem;font-weight:700;letter-spacing:0.04em;'>{summary['overall_status']}</div>
          <div class='kpi-sub'>{summary['months_tested']} months tested</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Basis Gate</div>
          <div class='kpi-value' style='color:{POSITIVE if summary["basis_gate_status"]=="PASS" else NEGATIVE}'>{summary['basis_gate_status']}</div>
          <div class='kpi-sub'>Level alignment</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Shape Gate</div>
          <div class='kpi-value' style='color:{POSITIVE if summary["shape_gate_status"]=="PASS" else NEGATIVE}'>{summary['shape_gate_status']}</div>
          <div class='kpi-sub'>Index-space curve fit</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Avg Abs Basis</div>
          <div class='kpi-value' style='color:{avg_col}'>{summary['avg_abs_basis_bp']:.2f} bp</div>
          <div class='kpi-sub'>Limit \u2264 {thr['max_avg_abs_basis_bps']:.0f} bp</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Max Basis</div>
          <div class='kpi-value' style='color:{max_col}'>{summary['max_abs_basis_bp']:.2f} bp</div>
          <div class='kpi-sub'>Limit \u2264 {thr['max_max_abs_basis_bps']:.0f} bp</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Within \u00b1{thr['tolerance_bps']:.0f} bp</div>
          <div class='kpi-value' style='color:{pct_col}'>{summary['pct_within_tolerance']:.0f}%</div>
          <div class='kpi-sub'>Need \u2265 {thr['min_pct_within_tolerance']:.0f}%</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Index R\u00b2 (Dense) / Rate R\u00b2</div>
          <div class='kpi-value' style='font-size:1.0rem;color:{idx_c_col}'>{index_curve_str} / <span style='color:{TEXT_SEC}'>{rate_r2_str}</span></div>
          <div class='kpi-sub'>Primary / Diagnostic</div>
        </div>
      </div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin-top:8px'>
        <div class='kpi-cell'><div class='kpi-micro'>Index R\u00b2 (Pillars)</div><div class='kpi-value' style='color:{idx_p_col}'>{index_pillar_str}</div><div class='kpi-sub'>Need \u2265 {thr['min_index_pillar_r2']:.2f}</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Index R\u00b2 (Dense Grid)</div><div class='kpi-value' style='color:{idx_c_col}'>{index_curve_str}</div><div class='kpi-sub'>Need \u2265 {thr['min_index_curve_r2']:.2f}</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Rate R\u00b2 (Diagnostic)</div><div class='kpi-value'>{rate_r2_str}</div><div class='kpi-sub'>Secondary diagnostic only</div></div>
      </div>
      <div style='padding:6px 12px 8px;font-size:0.68rem;color:{TEXT_MUTED};border-top:1px solid {BORDER}'>Index R\u00b2 measures curve shape alignment in index space (primary validation metric). Rate R\u00b2 is a secondary diagnostic.</div>
    </div>""", unsafe_allow_html=True)

    # ── Charts row ───────────────────────────────────────────────────────────
    months_str = parity_df["target_month"].dt.strftime("%b %Y").tolist()
    ch_left, ch_right = st.columns(2, gap="large")

    with ch_left:
        fig_curve = go.Figure()
        fig_curve.add_trace(go.Scatter(
            x=months_str, y=parity_df["oriel_rate_pct"].tolist(),
            name="ORIEL Implied YoY %", mode="lines+markers",
            line=dict(color=GOLD, width=2.5), marker=dict(color=GOLD, size=7),
        ))
        fig_curve.add_trace(go.Scatter(
            x=months_str, y=parity_df["otc_yoy_rate"].tolist(),
            name="OTC CPI Swap", mode="lines+markers",
            line=dict(color=SERIES2, width=2, dash="dot"), marker=dict(color=SERIES2, size=6),
        ))
        fig_curve.update_layout(**_layout(
            xaxis=_xaxis(title="Target Month"),
            yaxis=_yaxis(title="YoY %", ticksuffix="%"),
            height=ORIEL_INDEX_TAB_CHART_HEIGHT_PX,
            title=dict(text="ORIEL vs OTC Benchmark", font=dict(size=11, color="#8fa3b8"), x=0.01, xanchor="left"),
            margin=dict(l=72, r=36, t=42, b=64),
        ))
        st.plotly_chart(fig_curve, use_container_width=True, config=PLOTLY_CONFIG, theme=None,
                        key=f"parity_curve_{key_suffix}", height=ORIEL_INDEX_TAB_CHART_HEIGHT_PX)

    with ch_right:
        diff_vals = parity_df["diff_bps"].astype(float).tolist()
        within_vals = parity_df["within_tolerance"].tolist()
        fill_colors = ["rgba(34,197,94,0.55)" if w else "rgba(255,107,107,0.60)" for w in within_vals]
        line_colors = [POSITIVE_MUTED if w else NEGATIVE for w in within_vals]
        diff_customdata = [f"{v:+.1f}" for v in diff_vals]
        fig_basis = go.Figure()
        fig_basis.add_trace(go.Bar(
            x=months_str, y=diff_vals,
            customdata=diff_customdata,
            name="Basis (bp)",
            marker=dict(
                color=fill_colors,
                line=dict(color=line_colors, width=1.2),
            ),
            width=0.42,
            hovertemplate="<b>%{x}</b><br>Basis: %{customdata} bp<extra></extra>",
        ))
        fig_basis.add_hline(y=thr["tolerance_bps"],  line_dash="dot", line_color=GOLD, opacity=0.55)
        fig_basis.add_hline(y=-thr["tolerance_bps"], line_dash="dot", line_color=GOLD, opacity=0.55)
        fig_basis.add_hline(y=0, line_dash="solid",  line_color=SERIES_MUTE, opacity=0.4)
        fig_basis.update_layout(**_layout(
            xaxis=_xaxis(title="Target Month"),
            yaxis=_yaxis(title="Basis (bp)", ticksuffix=" bp"),
            height=ORIEL_INDEX_TAB_CHART_HEIGHT_PX,
            title=dict(text="Basis vs Tolerance Band", font=dict(size=11, color="#8fa3b8"), x=0.01, xanchor="left"),
            margin=dict(l=72, r=36, t=42, b=64),
            bargap=0.55,
        ))
        st.plotly_chart(fig_basis, use_container_width=True, config=PLOTLY_CONFIG, theme=None,
                        key=f"parity_basis_{key_suffix}", height=ORIEL_INDEX_TAB_CHART_HEIGHT_PX)

    # ── Index-Space Curve Alignment + Publish Gate / Parity Detail ───────────
    _idx_chart_h = max(280, int(ORIEL_INDEX_TAB_CHART_HEIGHT_PX * 0.85))

    gate_rows = [
        {"Check": "Avg abs basis",
         "Threshold": f"\u2264 {thr['max_avg_abs_basis_bps']:.1f} bp",
         "Observed":  f"{summary['avg_abs_basis_bp']:.2f} bp",
         "Status":    "Pass" if summary["conditions"]["avg_abs_basis_within_limit"] else "Fail"},
        {"Check": "Max abs basis",
         "Threshold": f"\u2264 {thr['max_max_abs_basis_bps']:.1f} bp",
         "Observed":  f"{summary['max_abs_basis_bp']:.2f} bp",
         "Status":    "Pass" if summary["conditions"]["max_abs_basis_within_limit"] else "Fail"},
        {"Check": f"Within \u00b1{thr['tolerance_bps']:.0f} bp",
         "Threshold": f"\u2265 {thr['min_pct_within_tolerance']:.0f}%",
         "Observed":  f"{summary['pct_within_tolerance']:.0f}%",
         "Status":    "Pass" if summary["conditions"]["pct_within_tolerance_sufficient"] else "Fail"},
        {"Check": "Index R\u00b2 (Pillars)",
         "Threshold": f"\u2265 {thr['min_index_pillar_r2']:.2f}",
         "Observed":  index_pillar_str,
         "Status":    "Pass" if summary["conditions"]["pillar_index_r2_sufficient"] else "Fail"},
        {"Check": "Index R\u00b2 (Dense Grid)",
         "Threshold": f"\u2265 {thr['min_index_curve_r2']:.2f}",
         "Observed":  index_curve_str,
         "Status":    "Pass" if summary["conditions"]["curve_index_r2_sufficient"] else "Fail"},
    ]
    gate_df  = pd.DataFrame(gate_rows)
    fail_idx = {i for i, r in gate_df.iterrows() if r["Status"] == "Fail"}

    _n_months = len(parity_df)
    _detail_h = DESK_TABLE_HEADER_PX + _n_months * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    _gate_h   = DESK_TABLE_HEADER_PX + len(gate_df) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    _gate_row_h = DESK_TABLE_ROW_PX

    latest    = parity_df.sort_values("target_month").iloc[0]
    basis_col = POSITIVE if abs(latest["diff_bps"]) <= thr["tolerance_bps"] else NEGATIVE

    _tables_total_h = _gate_h + _detail_h + 60
    _idx_chart_h = max(_idx_chart_h, _tables_total_h)

    col_idx_chart, col_idx_tables = st.columns([2, 1], gap="medium", vertical_alignment="top")

    with col_idx_chart:
        st.markdown("<div class='shdr' style='margin-top:8px'>Index-Space Curve Alignment</div>", unsafe_allow_html=True)
        grid_months = pd.to_datetime(grid_df["target_month"])
        fig_idx = go.Figure()
        fig_idx.add_trace(go.Scatter(
            x=grid_months, y=grid_df["oriel_implied_index"].tolist(),
            name="ORIEL Index Path", mode="lines",
            line=dict(color=GOLD, width=2.5),
        ))
        fig_idx.add_trace(go.Scatter(
            x=grid_months, y=grid_df["otc_implied_index"].tolist(),
            name="OTC Index Path", mode="lines",
            line=dict(color=SERIES2, width=2, dash="dot"),
        ))
        fig_idx.update_layout(**_layout(
            xaxis=_xaxis(title="Grid Date"),
            yaxis=_yaxis(title="Implied CPI Index"),
            height=_idx_chart_h,
            title=dict(text="Index-Space Oriel vs OTC (dense common grid)", font=dict(size=11, color="#8fa3b8"), x=0.01, xanchor="left"),
            margin=dict(l=72, r=36, t=42, b=48),
        ))
        st.plotly_chart(fig_idx, use_container_width=True, config=PLOTLY_CONFIG, theme=None,
                        key=f"parity_index_{key_suffix}", height=_idx_chart_h)

    with col_idx_tables:
        st.markdown("<div class='shdr' style='margin-top:8px'>Publish Gate</div>", unsafe_allow_html=True)
        _fig_gate = _plotly_desk_table(gate_df, flagged_rows=fail_idx, gold_column="Check",
                                       row_height=_gate_row_h)
        _fig_gate.update_layout(height=_gate_h)
        st.plotly_chart(_fig_gate, use_container_width=True, config=PLOTLY_CONFIG, theme=None,
                        key=f"parity_gate_{key_suffix}", height=_gate_h)

        st.markdown("<div class='shdr' style='margin-top:10px'>Parity Detail by Month</div>", unsafe_allow_html=True)
        disp = parity_df.copy()
        disp["target_month"] = disp["target_month"].dt.strftime("%b %Y")
        col_map = {
            "target_month":   "Target Month",
            "oriel_rate_pct": "ORIEL Rate %",
            "otc_yoy_rate":   "OTC Rate %",
            "diff_bps":       "Diff (bp)",
            "abs_diff_bps":   "Abs Diff (bp)",
            "status":         "Status",
        }
        disp = disp[[c for c in col_map if c in disp.columns]].rename(columns=col_map)
        for _nc in ("ORIEL Rate %", "OTC Rate %"):
            if _nc in disp.columns:
                disp[_nc] = disp[_nc].apply(lambda x: f"{x:.4f}")
        for _bc in ("Diff (bp)", "Abs Diff (bp)"):
            if _bc in disp.columns:
                disp[_bc] = disp[_bc].apply(lambda x: f"{x:.2f}")
        fail_rows   = {i for i, r in disp.iterrows() if r.get("Status") == "Fail"}
        _fig_detail = _plotly_desk_table(disp, flagged_rows=fail_rows, gold_column="ORIEL Rate %")
        _fig_detail.update_layout(height=_detail_h)
        st.plotly_chart(_fig_detail, use_container_width=True, config=PLOTLY_CONFIG, theme=None,
                        key=f"parity_detail_{key_suffix}", height=_detail_h)

    # Row 2: Front Month card | Methodology
    col_front, col_meth = st.columns([1, 1.55], gap="large", vertical_alignment="top")

    with col_front:
        st.markdown(f"""
        <div class='dcard' style='margin-top:4px'>
          <div class='kpi-micro' style='margin-bottom:6px'>{pd.Timestamp(latest['target_month']).strftime('%b %Y')} \u2014 front maturity</div>
          <div style='display:flex;gap:24px;align-items:flex-end'>
            <div>
              <div class='kpi-micro'>ORIEL Forward</div>
              <div class='kpi-value kpi-value--lead'>{latest['oriel_rate_pct']:.3f}%</div>
            </div>
            <div>
              <div class='kpi-micro'>OTC CPI Swap</div>
              <div class='kpi-value' style='font-size:1.1rem;color:{TEXT_SEC}'>{latest['otc_yoy_rate']:.3f}%</div>
            </div>
            <div>
              <div class='kpi-micro'>Basis</div>
              <div class='kpi-value' style='font-size:1.1rem;color:{basis_col}'>{latest['diff_bps']:+.2f} bp</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

    with col_meth:
        st.markdown(f"""
        <div class='note-box' style='margin-top:4px;font-size:0.71rem'>
          <strong>Benchmark:</strong> <code>{Path(bmark_path).name}</code><br>
          <strong>Standard:</strong> cleaned OTC CPI quote curve, not raw SDR prints<br>
          <strong>Tolerance:</strong> \u00b1{thr['tolerance_bps']:.0f} bp (locked)<br>
          <strong>Gate:</strong> basis gate + index-space R\u00b2 shape gate must pass before the curve is publishable<br>
          <strong>Shape metrics:</strong> dense-grid index R\u00b2 is primary; pillar rate R\u00b2 is diagnostic only
        </div>""", unsafe_allow_html=True)


# ── DTCC Term Calibration (reference, NOT parity) ────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def _cached_term_calibration():
    return _load_term_calibration(_TERM_CALIB_DIR)


def _make_term_structure_chart(by_tenor_df: pd.DataFrame, chart_height: int) -> go.Figure:
    """Term structure: median + notional-weighted avg rate by tenor (months on x)."""
    fig = go.Figure()
    if by_tenor_df is None or by_tenor_df.empty:
        fig.update_layout(**_layout(height=chart_height, margin=dict(l=64, r=22, t=22, b=72)))
        return fig

    df = by_tenor_df.sort_values("target_tenor_months").reset_index(drop=True)
    x_months = df["target_tenor_months"].astype(int).tolist()
    median_vals = df["median_rate_pct"].astype(float).tolist()
    nwavg_vals = df["notional_weighted_avg_rate_pct"].astype(float).tolist()
    labels = df["target_tenor_label"].astype(str).tolist()
    median_cd = [f"{v:.3f}" for v in median_vals]
    nwavg_cd = [f"{v:.3f}" for v in nwavg_vals]

    fig.add_trace(go.Scatter(
        x=x_months, y=nwavg_vals,
        customdata=nwavg_cd,
        mode="lines+markers", name="Notional-weighted avg",
        line=dict(color=GOLD, width=2.5),
        marker=dict(size=9, color=GOLD, line=dict(color=BG_SURFACE, width=1.5)),
        hovertemplate="<b>%{x} months</b><br>Notional-wtd avg: %{customdata}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x_months, y=median_vals,
        customdata=median_cd,
        mode="lines+markers", name="Median",
        line=dict(color=SERIES2, width=2, dash="dot"),
        marker=dict(size=7, color=SERIES2, line=dict(color=BG_SURFACE, width=1.5)),
        hovertemplate="<b>%{x} months</b><br>Median: %{customdata}%<extra></extra>",
    ))

    fig.update_layout(**_layout(
        height=chart_height,
        xaxis_title="Tenor (months)",
        yaxis_title="Fixed Rate (%)",
        showlegend=True,
        title=dict(
            text="DTCC OTC CPI swap term structure \u00b7 execution Dec 2025 \u2013 Feb 2026",
            font=dict(size=11, color=TEXT_SEC), x=0.01, xanchor="left", y=0.98, yanchor="top",
        ),
        margin=dict(l=64, r=22, t=52, b=72),
    ))
    fig.update_yaxes(ticksuffix="%", hoverformat=".3f")
    fig.update_xaxes(
        tickfont=dict(color=TEXT_PRI, size=11),
        title_font=dict(color=TEXT_SEC, size=11),
        tickmode="array",
        tickvals=x_months,
        ticktext=labels,
    )
    return fig


def _render_term_calibration_body() -> None:
    """Render the DTCC tenor calibration as a reference anchor view (not parity)."""
    if not TERM_CALIBRATION_AVAILABLE:
        st.error("Term calibration module not available. Place dtcc_term_calibration.py in the v7 root directory.")
        return
    try:
        bundle = _cached_term_calibration()
    except FileNotFoundError as exc:
        st.error(f"Term calibration artifacts missing: {exc}")
        return
    except Exception as exc:
        st.error(f"Term calibration error: {exc}")
        return

    by_tenor_full = bundle["by_tenor"]
    by_tenor_std  = _filter_standard_tenors(by_tenor_full)

    # ── Reference framing note ───────────────────────────────────────────────
    st.markdown(
        f"<div class='note-box' style='margin-top:4px;font-size:0.71rem'>"
        f"<strong>Calibration reference, not parity:</strong> live DTCC SDR public CPI swap data is dominated by tenor-based term trades "
        f"(1Y / 2Y / 3Y / 5Y / 10Y / 30Y) and does not map to a single monthly CPI bucket. This view shows where the real OTC term structure "
        f"is trading so it can anchor the Oriel curve, but it is <strong>not</strong> run through the monthly parity gate. "
        f"Term-rate parity (Option B) will replace this with a tenor-indexed comparison once the Oriel curve is extended beyond 6 months and a direct feed is wired in.</div>",
        unsafe_allow_html=True,
    )

    # ── Top KPI strip ────────────────────────────────────────────────────────
    total_trades = int(by_tenor_full["trade_count"].sum()) if "trade_count" in by_tenor_full.columns else 0
    total_notional = float(by_tenor_full["total_notional_usd"].sum()) if "total_notional_usd" in by_tenor_full.columns else 0.0
    n_std_tenors = int(len(by_tenor_std))
    n_all_tenors = int(len(by_tenor_full))
    exec_window_min = str(by_tenor_full["first_execution_utc"].min())[:10] if "first_execution_utc" in by_tenor_full.columns else "\u2014"
    exec_window_max = str(by_tenor_full["last_execution_utc"].max())[:10] if "last_execution_utc" in by_tenor_full.columns else "\u2014"
    if not by_tenor_std.empty:
        _w = by_tenor_std["total_notional_usd"].astype(float)
        _r = by_tenor_std["notional_weighted_avg_rate_pct"].astype(float)
        nwavg_std = float((_w * _r).sum() / _w.sum()) if _w.sum() > 0 else float("nan")
    else:
        nwavg_std = float("nan")

    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-top:10px;margin-bottom:12px'>
      <div class='kpi-strip-ribbon'>DTCC OTC CPI TERM STRUCTURE \u00b7 CALIBRATION REFERENCE \u00b7 {exec_window_min} \u2192 {exec_window_max}</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(6,minmax(0,1fr))'>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Source</div>
          <div class='kpi-value' style='font-size:0.92rem;'>DTCC SDR</div>
          <div class='kpi-sub'>Public CPI swaps</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Total Trades</div>
          <div class='kpi-value'>{total_trades:,}</div>
          <div class='kpi-sub'>{n_all_tenors} tenor buckets</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Total Notional</div>
          <div class='kpi-value kpi-value--lead'>${total_notional/1e9:,.2f}B</div>
          <div class='kpi-sub'>USD, all tenors</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Std-Tenor Wtd Avg</div>
          <div class='kpi-value' style='color:{GOLD};'>{nwavg_std:.3f}%</div>
          <div class='kpi-sub'>1Y/2Y/3Y/5Y/10Y/30Y</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Standard Tenors</div>
          <div class='kpi-value'>{n_std_tenors} / 6</div>
          <div class='kpi-sub'>Coverage of institutional pillars</div>
        </div>
        <div class='kpi-cell kpi-cell--pub'>
          <div class='kpi-micro'>Validation Mode</div>
          <div class='kpi-value' style='color:{TEXT_SEC};font-size:0.82rem;'>REFERENCE</div>
          <div class='kpi-sub'>Not parity gate</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Main row: term structure chart (left) + by-tenor cards (right) ───────
    left, right = st.columns([2, 1], gap="medium", vertical_alignment="top")

    with left:
        fig_term = _make_term_structure_chart(by_tenor_std, 388)
        st.plotly_chart(fig_term, width="stretch", config=PLOTLY_CONFIG, key="term_calib_chart")

    with right:
        front_row = by_tenor_std[by_tenor_std["target_tenor_label"] == "1Y"]
        if not front_row.empty:
            r = front_row.iloc[0]
            front_med = float(r["median_rate_pct"])
            front_nwavg = float(r["notional_weighted_avg_rate_pct"])
            front_count = int(r["trade_count"])
            front_notional = float(r["total_notional_usd"])
            front_min = float(r["min_rate_pct"])
            front_max = float(r["max_rate_pct"])
            st.markdown(f"""
            <div class='ip-wrap'>
              <div class='ip-header'>
                <span class='ip-header-label'>Front-Tenor Anchor (1Y)</span>
                <span class='ip-header-status' style='color:{GOLD};'>\u25cf Reference</span>
              </div>
              <div class='ip-highlight'>
                <span class='ip-hl-label'>Notional-Weighted Avg</span>
                <span class='ip-hl-value' style='color:{GOLD};'>{front_nwavg:.3f}%</span>
              </div>
              <div class='ip-body'>
                <div class='ip-row'><span class='ip-key'>Median Rate</span><span class='ip-val'>{front_med:.3f}%</span></div>
                <div class='ip-row'><span class='ip-key'>Range</span><span class='ip-val'>{front_min:.3f}% \u2013 {front_max:.3f}%</span></div>
                <div class='ip-row'><span class='ip-key'>Trade Count</span><span class='ip-val'>{front_count:,}</span></div>
                <div class='ip-row'><span class='ip-key'>Total Notional</span><span class='ip-val'>${front_notional/1e6:,.1f}M</span></div>
                <div class='ip-row'><span class='ip-key'>Tenor (months)</span><span class='ip-val'>12</span></div>
              </div>
            </div>""", unsafe_allow_html=True)

        belly = by_tenor_std[by_tenor_std["target_tenor_label"].isin(["5Y", "10Y", "30Y"])]
        belly_rows_html = ""
        for _, r in belly.iterrows():
            label = str(r["target_tenor_label"])
            nwavg = float(r["notional_weighted_avg_rate_pct"])
            count = int(r["trade_count"])
            notional_b = float(r["total_notional_usd"]) / 1e9
            belly_rows_html += (
                f"<div class='dislo-row'>"
                f"<span class='dislo-metric'>{label}</span>"
                f"<span class='dislo-val' style='color:{GOLD};'>{nwavg:.3f}%</span>"
                f"<span class='dislo-signal' style='color:{TEXT_MUTED};'>{count:,} trades \u00b7 ${notional_b:.2f}B</span>"
                f"</div>"
            )
        st.markdown(f"""
        <div class='dislo-wrap' style='margin-top:8px;'>
          <div class='dislo-header'><span class='dislo-title'>Belly &amp; Long End</span></div>
          {belly_rows_html}
        </div>""", unsafe_allow_html=True)

    # ── By-tenor desk table ──────────────────────────────────────────────────
    st.markdown("<div class='shdr oriel-section-gap'>By-Tenor Calibration Summary</div>", unsafe_allow_html=True)
    if not by_tenor_std.empty:
        tbl = by_tenor_std.copy()
        tbl["Tenor"]               = tbl["target_tenor_label"].astype(str)
        tbl["Trades"]              = tbl["trade_count"].astype(int).map(lambda v: f"{v:,}")
        tbl["Total Notional ($M)"] = (tbl["total_notional_usd"].astype(float) / 1e6).map(lambda v: f"{v:,.1f}")
        tbl["Median Rate (%)"]     = tbl["median_rate_pct"].astype(float).map(lambda v: f"{v:.3f}")
        tbl["Wtd Avg Rate (%)"]    = tbl["notional_weighted_avg_rate_pct"].astype(float).map(lambda v: f"{v:.3f}")
        tbl["Min (%)"]             = tbl["min_rate_pct"].astype(float).map(lambda v: f"{v:.3f}")
        tbl["Max (%)"]             = tbl["max_rate_pct"].astype(float).map(lambda v: f"{v:.3f}")
        tbl["Swap Format"]         = tbl["swap_format_mode"].astype(str)
        display_cols = [
            "Tenor", "Trades", "Total Notional ($M)",
            "Median Rate (%)", "Wtd Avg Rate (%)",
            "Min (%)", "Max (%)", "Swap Format",
        ]
        tbl_display = tbl[display_cols]
        _h = DESK_TABLE_HEADER_PX + len(tbl_display) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        _fig = _plotly_desk_table(tbl_display, gold_column="Wtd Avg Rate (%)")
        _fig.update_layout(height=_h)
        st.plotly_chart(_fig, width="stretch", config=PLOTLY_CONFIG, theme=None, key="term_calib_tbl", height=_h)

    # ── Footer copy ──────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='padding:6px 0 2px;font-size:0.68rem;color:{TEXT_MUTED};'>"
        f"Source: DTCC SDR public CPI swap dataset, normalized to tenor-parity input schema. cpi_lag_months is convention-inferred (3M) "
        f"and should be treated as inferred until a direct feed exposes an explicit lag field. Oddball tenors (43M, 7Y, 15Y, 20Y, 27Y) are "
        f"present in the underlying data but filtered from this view; see <code>data/dtcc_term_calibration/</code> for the full set.</div>",
        unsafe_allow_html=True,
    )


def render_parity_tab() -> None:
    with st.container(key="parity_ctrl"):
        st.markdown("""
        <div class='oriel-page-head'>
          <span class='oriel-page-title'>OTC Parity Validation</span>
          <span class='version-chip'>v1.0</span>
          <span class='version-chip' style='background:#1b2a3e;color:#7aa2f7;border-color:#2e4a72;'>+ Term Calibration Reference</span>
        </div>""", unsafe_allow_html=True)

    pt_term, pt_tight, pt_dtcc, pt_neg = st.tabs([
        "Term Calibration (DTCC Live)",
        "Reference OTC Benchmark",
        "DTCC SDR Calibration Sample",
        "Out-of-Tolerance Stress Case",
    ])
    with pt_term:
        _render_term_calibration_body()
    with pt_tight:
        _render_parity_body(str(TIGHTER_BENCHMARK_PATH), is_dtcc=False, key_suffix="tight")
    with pt_dtcc:
        _render_parity_body(str(DTCC_BENCHMARK_PATH), is_dtcc=True,  key_suffix="dtcc")
    with pt_neg:
        _render_parity_body(str(NEGATIVE_CONTROL_PATH), is_dtcc=False, key_suffix="neg")
