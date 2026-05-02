from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.cpi_basis_diagnostics import build_diagnostics
from analytics.tier1_fv_engine import (
    apply_microstructure_filters,
    build_forecastex_curve_from_constituents,
    build_kalshi_curve_from_constituents,
    blend_curves,
    compute_governed_blend_weights,
    compute_venue_weight_diagnostics,
    load_tier1_constituents,
    smooth_reference_curve,
)
from analytics.vol_surface_engine import build_vol_surface_artifacts
from ui.charts import _layout, _xaxis, _yaxis
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import _plotly_desk_table
from ui.tokens import (
    BG_ELEVATED, DESK_TABLE_HEADER_PX, DESK_TABLE_PAD_PX, DESK_TABLE_ROW_PX,
    GOLD, NEGATIVE, POSITIVE, POSITIVE_MUTED, PROJECT_ROOT,
    SERIES2, SERIES_MUTE, TEXT_MUTED, TEXT_SEC, WARNING,
)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_surface_inputs():
    data_dir = PROJECT_ROOT / "data"
    kalshi = apply_microstructure_filters(load_tier1_constituents(data_dir / "kalshi_constituents_current.csv"), "Kalshi")
    forecastex = apply_microstructure_filters(load_tier1_constituents(data_dir / "forecastex_constituents_current.csv"), "ForecastEx")
    kalshi_curve = build_kalshi_curve_from_constituents(kalshi)
    forecastex_curve = build_forecastex_curve_from_constituents(forecastex)
    k_diag = compute_venue_weight_diagnostics("Kalshi", 0.55, kalshi, kalshi_curve)
    f_diag = compute_venue_weight_diagnostics("ForecastEx", 0.45, forecastex, forecastex_curve)
    k_w, f_w = compute_governed_blend_weights(k_diag, f_diag)
    blended, _ = blend_curves(kalshi_curve, forecastex_curve, k_w, f_w, k_diag.eligible, f_diag.eligible)
    blended, _ = smooth_reference_curve(blended, pd.concat([kalshi, forecastex], ignore_index=True))
    diagnostics = build_diagnostics(kalshi, forecastex)
    return kalshi, forecastex, kalshi_curve, forecastex_curve, blended, diagnostics


def _fmt2(v):
    return f"{v:.2f}" if v is not None else "\u2014"


def _fmt1(v):
    return f"{v:.1f}" if v is not None else "\u2014"


def render_vol_surface_engine(snapshots, valuation_date):
    kalshi, forecastex, kalshi_curve, forecastex_curve, blended, diagnostics = _load_surface_inputs()
    artifacts = build_vol_surface_artifacts(snapshots, blended, pd.Timestamp(valuation_date), diagnostics.venue_comparison)

    st.markdown("<hr class='oriel-hr'>", unsafe_allow_html=True)
    st.markdown("<div class='shdr'>Volatility & Surface Engine</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.72rem;color:{TEXT_MUTED};margin:2px 0 10px;'>"
        "Binary-implied vol by maturity, venue dispersion, scenario sensitivity, component-vol framework.</div>",
        unsafe_allow_html=True,
    )

    # ── KPI strip ─────────────────────────────────────────────────────────
    s = artifacts.summary
    front_col = GOLD if (s['front_vol_pct'] or 0) > 0 else TEXT_MUTED
    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-bottom:10px'>
      <div class='kpi-strip-ribbon'>VOLATILITY SURFACE \u00b7 Binary-implied \u00b7 Parent CPI forward</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr))'>
        <div class='kpi-cell'><div class='kpi-micro'>Front Vol</div>
          <div class='kpi-value' style='color:{front_col};'>{_fmt2(s['front_vol_pct'])}%</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Back Vol</div>
          <div class='kpi-value'>{_fmt2(s['back_vol_pct'])}%</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Avg Vol</div>
          <div class='kpi-value'>{_fmt2(s['avg_vol_pct'])}%</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Avg Dispersion</div>
          <div class='kpi-value'>{_fmt1(s['dispersion_avg_bp'])} bp</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Peak Dispersion</div>
          <div class='kpi-value' style='color:{WARNING};'>{_fmt1(s['dispersion_peak_bp'])} bp</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Sub-tabs ──────────────────────────────────────────────────────────
    tab_surface, tab_disp, tab_scn, tab_comp = st.tabs([
        "Implied Vol Surface",
        "Venue Dispersion",
        "Forward / Vol Sensitivity",
        "Component Vol Framework",
    ])

    with tab_surface:
        surf = artifacts.implied_vol.copy()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=surf["target_month"], y=surf["parent_forward_pct"], mode="lines+markers",
            name="Parent CPI forward", line=dict(color=GOLD, width=2.2), marker=dict(size=6),
            yaxis="y1", hovertemplate="%{x|%b %Y}<br>Forward: %{y:.2f}%<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=surf["target_month"], y=surf["implied_vol_pct"], name="Binary-implied vol",
            marker=dict(color="rgba(107,154,255,0.45)", line=dict(color=SERIES2, width=1.0)),
            yaxis="y2", hovertemplate="%{x|%b %Y}<br>Vol: %{y:.2f}%<extra></extra>",
        ))
        fig.update_layout(**_layout(
            height=310,
            xaxis=_xaxis(title="Maturity"),
            yaxis=_yaxis(title="Parent CPI Forward (%)"),
        ))
        fig.update_layout(
            yaxis2=dict(title="Implied Vol (%)", overlaying="y", side="right", showgrid=False, tickfont=dict(color=TEXT_SEC)),
            bargap=0.45,
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="vol_surf_chart")

        show = surf.copy()
        show["target_month"] = show["target_month"].dt.strftime("%Y-%m")
        for c in ["parent_forward_pct", "implied_vol_pct"]:
            show[c] = show[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "\u2014")
        tfig = _plotly_desk_table(show, gold_column="implied_vol_pct")
        tfig.update_layout(height=DESK_TABLE_HEADER_PX + len(show) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX)
        st.plotly_chart(tfig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="vol_surf_tbl")

    with tab_disp:
        comp = diagnostics.venue_comparison.copy()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=comp["target_month"].dt.strftime("%b %Y"), y=comp["abs_curve_diff_bp"],
            marker=dict(color="rgba(255,107,107,0.45)", line=dict(color=NEGATIVE, width=1.0)),
            name="Abs venue diff (bp)", hovertemplate="%{x}<br>Dispersion: %{y:.1f} bp<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=comp["target_month"].dt.strftime("%b %Y"), y=comp["avg_confidence_score"],
            mode="lines+markers", name="Avg confidence",
            line=dict(color=POSITIVE_MUTED, width=2), marker=dict(size=6), yaxis="y2",
            hovertemplate="%{x}<br>Confidence: %{y:.1f}<extra></extra>",
        ))
        fig.update_layout(**_layout(
            height=310,
            xaxis=_xaxis(title="Maturity"),
            yaxis=_yaxis(title="Abs Diff (bp)"),
        ))
        fig.update_layout(yaxis2=dict(title="Confidence", overlaying="y", side="right", showgrid=False, range=[0, 100]))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="vol_disp_chart")

        show = comp[["target_month", "abs_curve_diff_bp", "avg_confidence_score", "avg_spread_bp", "liquidity_flag"]].copy()
        show["target_month"] = show["target_month"].dt.strftime("%Y-%m")
        for c in ["abs_curve_diff_bp", "avg_confidence_score", "avg_spread_bp"]:
            show[c] = show[c].map(lambda x: f"{x:.2f}" if pd.notna(x) else "\u2014")
        tfig = _plotly_desk_table(show, gold_column="abs_curve_diff_bp")
        tfig.update_layout(height=DESK_TABLE_HEADER_PX + len(show) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX)
        st.plotly_chart(tfig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="vol_disp_tbl")

    with tab_scn:
        surf = artifacts.implied_vol.copy()
        options = {pd.Timestamp(tm).strftime("%b %Y"): pd.Timestamp(tm) for tm in surf["target_month"]}
        st.markdown("<div class='ctrl-vd-label'>Scenario Maturity</div>", unsafe_allow_html=True)
        label = st.selectbox("Scenario maturity", list(options.keys()), index=0, key="vol_surface_scn_maturity", label_visibility="collapsed")
        selected_month = options[label]
        scenario = artifacts.scenario_grid.loc[artifacts.scenario_grid["target_month"] == selected_month].copy()
        pivot = scenario.pivot(index="forward_shift_bp", columns="vol_multiplier", values="scenario_event_price").sort_index(ascending=False)
        heat = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[f"{c:.1f}x" for c in pivot.columns],
            y=[f"{int(i):+d} bp" for i in pivot.index],
            colorscale="Blues", zmin=0, zmax=1,
            hovertemplate="Forward shift %{y}<br>Vol %{x}<br>Event price %{z:.3f}<extra></extra>",
        ))
        heat.update_layout(**_layout(
            height=280,
            xaxis=_xaxis(title="Vol multiplier"),
            yaxis=_yaxis(title="Forward shift"),
        ))
        st.plotly_chart(heat, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="vol_scn_heat")

        show = scenario[["forward_shift_bp", "vol_multiplier", "scenario_forward_pct", "scenario_vol_pct", "scenario_event_price"]].copy()
        for c in ["scenario_forward_pct", "scenario_vol_pct", "scenario_event_price"]:
            show[c] = show[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "\u2014")
        tfig = _plotly_desk_table(show, gold_column="scenario_event_price")
        h = DESK_TABLE_HEADER_PX + min(len(show), 6) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        tfig.update_layout(height=h)
        st.plotly_chart(tfig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="vol_scn_tbl")

    with tab_comp:
        left, right = st.columns([1, 2], gap="medium")
        with left:
            st.markdown("<div class='shdr'>Component Parameters</div>", unsafe_allow_html=True)
            med_beta = st.slider("Medical CPI beta", 0.6, 1.6, 1.15, 0.05, key="med_beta")
            med_rho = st.slider("Medical CPI corr", 0.2, 0.95, 0.72, 0.01, key="med_rho")
            shelter_beta = st.slider("Shelter beta", 0.6, 1.4, 0.95, 0.05, key="shelter_beta")
            shelter_rho = st.slider("Shelter corr", 0.2, 0.99, 0.88, 0.01, key="shelter_rho")
            core_beta = st.slider("Core svc ex-shelter beta", 0.6, 1.6, 1.05, 0.05, key="core_beta")
            core_rho = st.slider("Core svc ex-shelter corr", 0.2, 0.99, 0.81, 0.01, key="core_rho")
        with right:
            custom_components = build_vol_surface_artifacts(
                snapshots, blended, pd.Timestamp(valuation_date), diagnostics.venue_comparison,
            )
            from analytics.vol_surface_engine import build_component_vol_framework
            compdf = build_component_vol_framework(
                custom_components.implied_vol,
                [
                    {"component": "Medical CPI", "beta_to_parent": med_beta, "correlation": med_rho},
                    {"component": "Shelter CPI", "beta_to_parent": shelter_beta, "correlation": shelter_rho},
                    {"component": "Core Svc ex Shelter", "beta_to_parent": core_beta, "correlation": core_rho},
                ],
            )
            fig = go.Figure()
            for name, color in [("Medical CPI", GOLD), ("Shelter CPI", SERIES_MUTE), ("Core Svc ex Shelter", SERIES2)]:
                sub = compdf[compdf["component"] == name]
                fig.add_trace(go.Scatter(
                    x=sub["target_month"], y=sub["component_implied_vol_pct"], mode="lines+markers",
                    name=name, line=dict(width=2.2, color=color), marker=dict(size=6),
                    hovertemplate="%{x|%b %Y}<br>%{y:.2f}%<extra></extra>",
                ))
            fig.update_layout(**_layout(
                height=310,
                xaxis=_xaxis(title="Maturity"),
                yaxis=_yaxis(title="Component Implied Vol (%)"),
            ))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="vol_comp_chart")

            show = compdf.copy()
            show["target_month"] = show["target_month"].dt.strftime("%Y-%m")
            for c in ["parent_vol_pct", "component_implied_vol_pct"]:
                if c in show.columns:
                    show[c] = show[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "\u2014")
            tfig = _plotly_desk_table(show, gold_column="component_implied_vol_pct")
            tfig.update_layout(height=DESK_TABLE_HEADER_PX + len(show) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX)
            st.plotly_chart(tfig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="vol_comp_tbl")

    st.markdown(
        f"<div style='font-size:0.68rem;color:{TEXT_MUTED};margin-top:4px;'>"
        "Binary-implied vols approximated by inverting threshold prices against the parent CPI forward. "
        "Component framework uses user-controlled beta/correlation assumptions \u2014 placeholder for roadmap discussions.</div>",
        unsafe_allow_html=True,
    )
