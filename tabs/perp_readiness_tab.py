"""
tabs/perp_readiness_tab.py — Oriel CPI Basis (Tier 1 Perp Readiness) tab.

Extracted from app.py lines ~2473-3396.
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

from analytics.tier1_fv_engine import (
    BlendMetadata, Tier1Snapshot, build_forecastex_curve_from_constituents,
    build_kalshi_curve_from_constituents, build_tier1_snapshot, blend_curves,
    load_tier1_constituents, load_tier1_curve,
    VenueCurvePoint, BlendedReferencePoint, VenueWeightDiagnostics,
    VenueFreshnessSummary, BlendedFreshnessSummary,
    compute_distribution_metrics, compute_blended_reference_points,
    compute_venue_weight_diagnostics, compute_governed_blend_weights,
    build_venue_freshness_summary, build_blended_freshness_summary,
    generate_freshness_commentary, apply_microstructure_filters,
    smooth_reference_curve, compute_weight_calibration_summary,
    compute_enhanced_publishability, generate_trade_ideas,
)
from analytics.cpi_basis_diagnostics import build_diagnostics


_TIER1_DATA_DIR = PROJECT_ROOT / "data"


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_tier1_curves():
    """Governed CPI blend flow for the Oriel CPI Basis tab."""
    kalshi_cur_const = apply_microstructure_filters(
        load_tier1_constituents(_TIER1_DATA_DIR / "kalshi_constituents_current.csv"), "Kalshi"
    )
    forecastex_cur_const = apply_microstructure_filters(
        load_tier1_constituents(_TIER1_DATA_DIR / "forecastex_constituents_current.csv"), "ForecastEx"
    )
    kalshi_pri_const = apply_microstructure_filters(
        load_tier1_constituents(_TIER1_DATA_DIR / "kalshi_constituents_prior.csv"), "Kalshi"
    )
    forecastex_pri_const = apply_microstructure_filters(
        load_tier1_constituents(_TIER1_DATA_DIR / "forecastex_constituents_prior.csv"), "ForecastEx"
    )

    kalshi_curve = build_kalshi_curve_from_constituents(kalshi_cur_const)
    forecastex_curve = build_forecastex_curve_from_constituents(forecastex_cur_const)
    prior_kalshi_curve = build_kalshi_curve_from_constituents(kalshi_pri_const)
    prior_forecastex_curve = build_forecastex_curve_from_constituents(forecastex_pri_const)

    current_k_diag = compute_venue_weight_diagnostics("Kalshi", 0.55, kalshi_cur_const, kalshi_curve)
    current_f_diag = compute_venue_weight_diagnostics("ForecastEx", 0.45, forecastex_cur_const, forecastex_curve)
    current_k_wt, current_f_wt = compute_governed_blend_weights(current_k_diag, current_f_diag)

    prior_k_diag = compute_venue_weight_diagnostics("Kalshi", 0.55, kalshi_pri_const, prior_kalshi_curve)
    prior_f_diag = compute_venue_weight_diagnostics("ForecastEx", 0.45, forecastex_pri_const, prior_forecastex_curve)
    prior_k_wt, prior_f_wt = compute_governed_blend_weights(prior_k_diag, prior_f_diag)

    current_blended_curve, current_blend_meta = blend_curves(
        kalshi_curve, forecastex_curve,
        kalshi_weight=current_k_wt, forecastex_weight=current_f_wt,
        kalshi_eligible=current_k_diag.eligible,
        forecastex_eligible=current_f_diag.eligible,
    )
    current_blended_curve, current_smoothing = smooth_reference_curve(
        current_blended_curve, pd.concat([kalshi_cur_const, forecastex_cur_const], ignore_index=True)
    )
    prior_blended_curve, prior_blend_meta = blend_curves(
        prior_kalshi_curve, prior_forecastex_curve,
        kalshi_weight=prior_k_wt, forecastex_weight=prior_f_wt,
        kalshi_eligible=prior_k_diag.eligible,
        forecastex_eligible=prior_f_diag.eligible,
    )
    prior_blended_curve, prior_smoothing = smooth_reference_curve(
        prior_blended_curve, pd.concat([kalshi_pri_const, forecastex_pri_const], ignore_index=True)
    )

    return {
        "kalshi_curve": kalshi_curve,
        "forecastex_curve": forecastex_curve,
        "current_curve": current_blended_curve,
        "prior_curve": prior_blended_curve,
        "blend_meta": current_blend_meta,
        "prior_blend_meta": prior_blend_meta,
        "kalshi_constituents": kalshi_cur_const,
        "forecastex_constituents": forecastex_cur_const,
        "kalshi_diag": current_k_diag,
        "forecastex_diag": current_f_diag,
        "smoothing_diag": current_smoothing,
        "prior_smoothing_diag": prior_smoothing,
    }


def _make_perp_readiness_curve_chart(
    current: pd.DataFrame,
    prior: pd.DataFrame | None,
    fv_horizon_days: int,
    fv_index: float,
    chart_height: int,
) -> go.Figure:
    fig = go.Figure()
    if prior is not None:
        fig.add_trace(go.Scatter(
            x=prior["days_from_valuation"],
            y=prior["index_level"],
            mode="lines",
            name="Prior Curve",
            line=dict(color=SERIES_MUTE, width=1.5, dash="dash"),
            hovertemplate="%{x}d \u00b7 Prior: %{y:.4f}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=current["days_from_valuation"],
        y=current["index_level"],
        mode="lines+markers",
        name="Current Curve",
        line=dict(color=GOLD, width=2.5),
        marker=dict(size=7, color=GOLD, line=dict(color=BG_APP, width=1.5)),
        hovertemplate="%{x}d \u00b7 Index: %{y:.4f}<extra></extra>",
    ))
    fig.add_vline(x=fv_horizon_days, line_width=1.5, line_dash="dash", line_color=SERIES2)
    fig.add_hline(y=fv_index, line_width=1, line_dash="dot", line_color=SERIES2)
    fig.add_annotation(
        x=fv_horizon_days, y=fv_index,
        text=f"FV @ {fv_horizon_days}d = {fv_index:.4f}",
        showarrow=True, arrowhead=2, ax=52, ay=-38,
        font=dict(color=TEXT_PRI, size=11),
        arrowcolor=SERIES2,
        bgcolor=BG_ELEVATED, bordercolor=BORDER_STR,
    )
    fig.update_layout(**_layout(
        height=chart_height,
        xaxis_title="Days from Valuation",
        yaxis_title="Implied Index Level",
        xaxis=dict(showgrid=True, gridcolor=GRID_SOFT, linecolor=BORDER, tickcolor=BORDER, zeroline=False, tickfont=dict(color=TEXT_SEC)),
        yaxis=dict(showgrid=True, gridcolor=GRID_SOFT, linecolor=BORDER, tickcolor=BORDER, zeroline=False, tickfont=dict(color=TEXT_SEC)),
    ))
    return fig


def _make_spot_fv_perp_bar(
    spot_index: float,
    fv_index: float,
    perp_price: float,
    chart_height: int,
) -> go.Figure:
    fig = go.Figure()
    perp_above = perp_price >= fv_index
    _fill_spot  = "rgba(75,91,112,0.55)"
    _fill_fv    = "rgba(212,168,90,0.55)"
    _fill_perp  = "rgba(34,197,94,0.55)" if perp_above else "rgba(255,107,107,0.60)"
    _line_perp  = POSITIVE_MUTED if perp_above else NEGATIVE
    vals = [spot_index, fv_index, perp_price]
    customdata = [f"{v:.4f}" for v in vals]
    fig.add_trace(go.Bar(
        x=["Spot", "Fair Value", "Sim. Perp"],
        y=vals,
        customdata=customdata,
        marker=dict(
            color=[_fill_spot, _fill_fv, _fill_perp],
            line=dict(color=[SERIES_MUTE, GOLD, _line_perp], width=1.2),
        ),
        hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
        name="Level",
        width=0.42,
    ))
    fig.update_layout(**_layout(
        height=chart_height,
        yaxis_title="Index Level",
        showlegend=False,
        xaxis=dict(showgrid=False, linecolor=BORDER, tickcolor=BORDER, zeroline=False, tickfont=dict(color=TEXT_SEC)),
        yaxis=dict(showgrid=True, gridcolor=GRID_SOFT, linecolor=BORDER, tickcolor=BORDER, zeroline=False, tickfont=dict(color=TEXT_SEC)),
        margin=dict(l=52, r=20, t=20, b=40),
    ))
    return fig


def _make_dispersion_chart(diag_df: pd.DataFrame, chart_height: int) -> go.Figure:
    fig = go.Figure()
    x = diag_df["target_month"].dt.strftime("%b %Y")
    vals = diag_df["abs_curve_diff_bp"].fillna(0).astype(float).tolist()
    median_val = diag_df["abs_curve_diff_bp"].median()
    fill_colors = ["rgba(255,107,107,0.55)" if v >= median_val else "rgba(212,168,90,0.55)" for v in vals]
    line_colors = [NEGATIVE if v >= median_val else GOLD for v in vals]
    customdata = [f"{v:.1f}" for v in vals]
    fig.add_trace(go.Bar(
        x=x,
        y=vals,
        customdata=customdata,
        name="Venue Dispersion",
        marker=dict(
            color=fill_colors,
            line=dict(color=line_colors, width=1.2),
        ),
        width=0.5,
        hovertemplate="<b>%{x}</b><br>Dispersion: %{customdata} bp<extra></extra>",
    ))
    fig.update_layout(**_layout(
        height=chart_height,
        xaxis_title="Maturity",
        yaxis_title="Abs Diff (bp)",
        showlegend=False,
        margin=dict(l=64, r=22, t=22, b=72),
        bargap=0.5,
    ))
    fig.update_xaxes(tickfont=dict(color=TEXT_PRI, size=11), title_font=dict(color=TEXT_SEC, size=11))
    fig.update_yaxes(title_font=dict(color=TEXT_SEC, size=11), ticksuffix=" bp")
    return fig


def _make_confidence_scatter(diag_df: pd.DataFrame, chart_height: int) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=diag_df["avg_confidence_score"],
        y=diag_df["abs_curve_diff_bp"],
        mode="markers",
        text=diag_df["target_month"].dt.strftime("%b %Y"),
        marker=dict(
            size=11,
            color=diag_df["avg_spread_bp"],
            colorscale=[[0.0, SERIES2], [0.5, GOLD], [1.0, NEGATIVE]],
            showscale=False,
            line=dict(color=BORDER, width=1),
        ),
        hovertemplate="%{text}<br>Confidence: %{x:.1f}<br>Dispersion: %{y:.1f} bp<extra></extra>",
        name="Maturity",
    ))
    fig.update_layout(**_layout(
        height=chart_height,
        xaxis_title="Avg Confidence Score",
        yaxis_title="Abs Diff (bp)",
        showlegend=False,
        margin=dict(l=64, r=22, t=22, b=72),
    ))
    fig.update_xaxes(tickfont=dict(color=TEXT_PRI, size=11), title_font=dict(color=TEXT_SEC, size=11))
    fig.update_yaxes(title_font=dict(color=TEXT_SEC, size=11))
    return fig


def _format_diag_tables(diag_bundle):
    import pandas as _pd
    maturity = diag_bundle.maturity_level.copy()
    maturity["target_month"] = maturity["target_month"].dt.strftime("%Y-%m")
    maturity["last_update_time"] = _pd.to_datetime(maturity["last_update_time"]).dt.strftime("%Y-%m-%d %H:%M")
    maturity = maturity.rename(columns={
        "target_month": "Target Month",
        "venue": "Venue",
        "raw_contract_implied_expected_cpi": "Raw Impl. CPI (%)",
        "bid_ask_spread_bp": "Bid/Ask Spread (bp)",
        "depth_size": "Depth / Size",
        "open_interest": "Open Interest",
        "last_update_time": "Last Update",
        "confidence_score": "Confidence",
    })
    for col in ["Raw Impl. CPI (%)", "Bid/Ask Spread (bp)", "Depth / Size", "Open Interest", "Confidence"]:
        if col in maturity.columns:
            maturity[col] = maturity[col].map(lambda x: f"{x:.2f}" if _pd.notna(x) else "")

    compare = diag_bundle.venue_comparison.copy()
    compare["target_month"] = compare["target_month"].dt.strftime("%Y-%m")
    keep = [
        "target_month", "days_from_valuation",
        "kalshi_raw_contract_implied_expected_cpi",
        "forecastex_raw_contract_implied_expected_cpi",
        "abs_curve_diff_bp",
        "kalshi_confidence_score",
        "forecastex_confidence_score",
        "liquidity_flag",
    ]
    compare = compare[[c for c in keep if c in compare.columns]].rename(columns={
        "target_month": "Target Month",
        "days_from_valuation": "Days",
        "kalshi_raw_contract_implied_expected_cpi": "Kalshi CPI (%)",
        "forecastex_raw_contract_implied_expected_cpi": "ForecastEx CPI (%)",
        "abs_curve_diff_bp": "Abs Diff (bp)",
        "kalshi_confidence_score": "Kalshi Conf.",
        "forecastex_confidence_score": "ForecastEx Conf.",
        "liquidity_flag": "Dominant Issue",
    })
    for col in ["Kalshi CPI (%)", "ForecastEx CPI (%)", "Abs Diff (bp)", "Kalshi Conf.", "ForecastEx Conf."]:
        if col in compare.columns:
            compare[col] = compare[col].map(lambda x: f"{x:.2f}" if _pd.notna(x) else "")

    tests = diag_bundle.scenario_tests.copy().rename(columns={
        "test": "Test",
        "rule": "Rule",
        "avg_dispersion_bp": "Avg Dispersion (bp)",
        "coverage_maturities": "Coverage",
        "delta_vs_baseline_bp": "\u0394 vs Baseline (bp)",
    })
    for col in ["Avg Dispersion (bp)", "\u0394 vs Baseline (bp)"]:
        if col in tests.columns:
            tests[col] = tests[col].map(lambda x: f"{x:.2f}" if _pd.notna(x) else "n/a")
    return maturity, compare, tests


def _render_basis_diagnostics(diag_bundle, chart_height: int = 330) -> None:
    summary = diag_bundle.summary
    concentrated = summary.get("dispersion_concentrated_in_least_liquid")
    spread_narrows = summary.get("spread_filter_narrows_gap")
    stale_narrows = summary.get("drop_stale_narrows_gap")
    conf_narrows = summary.get("confidence_weighting_narrows_gap")

    bool_fmt = lambda x: "Yes" if x is True else "No" if x is False else "n/a"
    source_label = "Live venue quote fields" if diag_bundle.metadata.get("uses_live_quote_fields") else "Indicative proxy diagnostics from constituent set"

    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-top:8px;margin-bottom:12px'>
      <div class='kpi-strip-ribbon'>VENUE DIAGNOSTICS \u00b7 Why Oriel should blend venue surfaces rather than present one venue as truth</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr))'>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Avg Venue Dispersion</div>
          <div class='kpi-value'>{summary.get('avg_dispersion_bp', float('nan')):.1f} bp</div>
          <div class='kpi-sub'>{source_label}</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Max Venue Dispersion</div>
          <div class='kpi-value'>{summary.get('max_dispersion_bp', float('nan')):.1f} bp</div>
          <div class='kpi-sub'>Largest maturity gap</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Least-Liquid Concentration</div>
          <div class='kpi-value'>{summary.get('least_liquid_high_dispersion_share', 0.0) * 100:.0f}%</div>
          <div class='kpi-sub'>High-dispersion maturities in weaker liquidity bucket</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Spread Filter Narrows Gap?</div>
          <div class='kpi-value' style='color:{POSITIVE if spread_narrows else NEGATIVE if spread_narrows is False else TEXT_SEC};'>{bool_fmt(spread_narrows)}</div>
          <div class='kpi-sub'>Spread \u2264 {diag_bundle.metadata['spread_threshold_bp']:.1f} bp</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Confidence Weighting Narrows Gap?</div>
          <div class='kpi-value' style='color:{POSITIVE if conf_narrows else NEGATIVE if conf_narrows is False else TEXT_SEC};'>{bool_fmt(conf_narrows)}</div>
          <div class='kpi-sub'>Liquidity / freshness aware</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f"<div class='note-box' style='margin-top:4px;font-size:0.71rem'>"
        f"<strong>Diagnostic framing:</strong> Tests whether venue disagreement is concentrated in less liquid maturities and whether the shape gap narrows under cleaner quote rules. "
        f"<strong>Least-liquid concentration:</strong> {bool_fmt(concentrated)} \u00b7 "
        f"<strong>Drop stale narrows gap:</strong> {bool_fmt(stale_narrows)} \u00b7 "
        f"<strong>Source mode:</strong> {source_label}."
        f"</div>",
        unsafe_allow_html=True,
    )

    ch_l, ch_r = st.columns(2, gap="large")
    with ch_l:
        fig = _make_dispersion_chart(diag_bundle.venue_comparison, chart_height)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="basis_diag_disp", height=chart_height)
    with ch_r:
        fig = _make_confidence_scatter(diag_bundle.venue_comparison, chart_height)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="basis_diag_scatter", height=chart_height)

    maturity_tbl, compare_tbl, tests_tbl = _format_diag_tables(diag_bundle)
    tab1, tab2, tab3 = st.tabs(["By maturity", "Cross-venue comparison", "Diagnostic tests"])
    with tab1:
        _h = DESK_TABLE_HEADER_PX + len(maturity_tbl) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        _fig = _plotly_desk_table(maturity_tbl, gold_column="Raw Impl. CPI (%)")
        _fig.update_layout(height=_h)
        st.plotly_chart(_fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="basis_diag_maturity_tbl", height=_h)
    with tab2:
        flagged = {i for i, v in enumerate(compare_tbl["Dominant Issue"].tolist()) if v != "Healthy"} if "Dominant Issue" in compare_tbl.columns else set()
        _h = DESK_TABLE_HEADER_PX + len(compare_tbl) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        _fig = _plotly_desk_table(compare_tbl, flagged_rows=flagged, gold_column="Abs Diff (bp)")
        _fig.update_layout(height=_h)
        st.plotly_chart(_fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="basis_diag_compare_tbl", height=_h)
    with tab3:
        flagged = {i for i, v in enumerate(tests_tbl["\u0394 vs Baseline (bp)"].tolist()) if v not in ("n/a", "0.00") and float(v) > 0}
        _h = DESK_TABLE_HEADER_PX + len(tests_tbl) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        _fig = _plotly_desk_table(tests_tbl, flagged_rows=flagged, gold_column="Avg Dispersion (bp)")
        _fig.update_layout(height=_h)
        st.plotly_chart(_fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="basis_diag_tests_tbl", height=_h)


def render_perp_readiness_tab() -> None:
    # ── Controls ─────────────────────────────────────────────────────────────
    with st.container(key="t1_ctrl"):
        cl, cr_fv, cr_bp = st.columns([4, 1.4, 1.4], gap="small", vertical_alignment="center", border=False)
        with cl:
            st.markdown(f"""
            <div class='oriel-page-head'>
              <span class='oriel-page-title'>Oriel CPI Basis</span>
              <span class='version-chip'>v0.1.0-tier1</span>
              <span class='version-chip' style='background:#1b2a3e;color:#7aa2f7;border-color:#2e4a72;'>Tier 1 \u00b7 Spot / FV / Carry / Basis</span>
            </div>""", unsafe_allow_html=True)
        with cr_fv:
            fv_horizon = st.number_input(
                "FV Horizon (days)", min_value=1, max_value=180, value=30, step=1,
                key="t1_fv_horizon", label_visibility="visible",
            )
        with cr_bp:
            perp_basis = st.number_input(
                "Perp Basis (bp vs FV)", min_value=-50.0, max_value=50.0, value=12.0, step=1.0,
                key="t1_perp_basis", label_visibility="visible",
            )

    st.markdown(
        "<div style='font-size:0.75rem;color:#8fa3b8;margin:4px 0 8px;'>"
        "Forward curve converted into a tradable reference framework: fair value at a configurable horizon, "
        "spot vs FV vs simulated perp, basis, and annualized carry. "
        "Tier 1 reference layer for CPI basis and perpification of prediction-market contracts (Hyperliquid / AX).</div>",
        unsafe_allow_html=True,
    )

    dx1, dx2, dx3 = st.columns([1.2, 1.2, 3.0], gap="small")
    with dx1:
        st.number_input(
            "Diag spread threshold (bp)",
            min_value=1.0, max_value=25.0, value=12.0, step=1.0,
            key="t1_diag_spread_threshold",
        )
    with dx2:
        st.number_input(
            "Diag stale cutoff (min)",
            min_value=1, max_value=120, value=15, step=1,
            key="t1_diag_stale_minutes",
        )
    with dx3:
        st.markdown(
            f"<div style='font-size:0.68rem;color:{TEXT_MUTED};padding-top:26px;'>"
            "Diagnostics test whether venue disagreement is concentrated in thin maturities, and whether "
            "the shape gap narrows under tighter quote hygiene or confidence-aware weighting."
            "</div>",
            unsafe_allow_html=True,
        )

    diag_spread_threshold = st.session_state.get("t1_diag_spread_threshold", 12.0)
    diag_stale_minutes    = st.session_state.get("t1_diag_stale_minutes", 15)

    try:
        tier1_bundle = _cached_tier1_curves()
        current_curve = tier1_bundle["current_curve"]
        prior_curve = tier1_bundle["prior_curve"]
        blend_meta = tier1_bundle["blend_meta"]
        diag_bundle = build_diagnostics(
            tier1_bundle["kalshi_constituents"],
            tier1_bundle["forecastex_constituents"],
            spread_threshold_bp=float(diag_spread_threshold),
            stale_after_min=int(diag_stale_minutes),
        )
    except Exception as exc:
        st.error(f"Tier 1 data load error: {exc}")
        return

    snap = build_tier1_snapshot(current_curve, int(fv_horizon), float(perp_basis), blend_meta)

    # ── Hardening: distribution, weight diagnostics, freshness ───────────
    kalshi_constituents = tier1_bundle["kalshi_constituents"]
    forecastex_constituents = tier1_bundle["forecastex_constituents"]

    k_dist_pts = compute_distribution_metrics(tier1_bundle["kalshi_curve"], kalshi_constituents)
    f_dist_pts = compute_distribution_metrics(tier1_bundle["forecastex_curve"], forecastex_constituents)
    blended_ref_pts = compute_blended_reference_points(
        current_curve, tier1_bundle["kalshi_curve"], tier1_bundle["forecastex_curve"],
    )

    k_weight_diag = compute_venue_weight_diagnostics(
        "Kalshi", 0.55, kalshi_constituents, tier1_bundle["kalshi_curve"],
    )
    f_weight_diag = compute_venue_weight_diagnostics(
        "ForecastEx", 0.45, forecastex_constituents, tier1_bundle["forecastex_curve"],
    )
    k_eff_wt, f_eff_wt = compute_governed_blend_weights(k_weight_diag, f_weight_diag)

    k_freshness = build_venue_freshness_summary(kalshi_constituents, "Kalshi")
    f_freshness = build_venue_freshness_summary(forecastex_constituents, "ForecastEx")
    blended_freshness = build_blended_freshness_summary(k_freshness, f_freshness)
    freshness_commentary = generate_freshness_commentary(blended_freshness)
    smoothing_diag = tier1_bundle["smoothing_diag"]
    weight_calibration = compute_weight_calibration_summary(k_weight_diag, f_weight_diag)
    enhanced_publishability, enhanced_confidence, enhanced_conf_score, conf_breakdown = compute_enhanced_publishability(
        current_curve, blend_meta, k_weight_diag, f_weight_diag, blended_freshness
    )
    snap.publishability_label = enhanced_publishability
    snap.confidence_label = enhanced_confidence
    snap.confidence_score_pct = enhanced_conf_score
    trade_ideas = generate_trade_ideas(snap, current_curve, k_weight_diag, f_weight_diag)

    basis_col  = POSITIVE if snap.basis_bp >= 0 else NEGATIVE
    carry_col  = POSITIVE if snap.annualized_carry_bp >= 0 else NEGATIVE
    term_col   = POSITIVE if snap.term_structure_pct >= 0 else NEGATIVE

    # ── ORIEL 3M CPI FORWARD INDEX strip ─────────────────────────────────────
    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-bottom:12px'>
      <div class='kpi-strip-ribbon'>ORIEL 3M CPI FORWARD INDEX \u00b7 Governed blend from Kalshi + ForecastEx constituent curves</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(6,minmax(0,1fr))'>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Official Print / Base Index</div>
          <div class='kpi-value'>{snap.official_index_print:.2f}</div>
          <div class='kpi-sub'>Base 100 reference</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>1M Implied</div>
          <div class='kpi-value kpi-value--lead'>{snap.implied_1m_yoy_pct:.2f}%</div>
          <div class='kpi-sub'>30-day forward CPI view</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>3M Implied</div>
          <div class='kpi-value kpi-value--lead'>{snap.implied_3m_yoy_pct:.2f}%</div>
          <div class='kpi-sub'>Featured forward reference</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>6M Implied</div>
          <div class='kpi-value'>{snap.implied_6m_yoy_pct:.2f}%</div>
          <div class='kpi-sub'>180-day forward CPI view</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Term Structure</div>
          <div class='kpi-value' style='color:{term_col};'>{snap.term_structure_pct:+.2f}%</div>
          <div class='kpi-sub'>6M minus 1M implied</div>
        </div>
        <div class='kpi-cell kpi-cell--pub'>
          <div class='kpi-micro'>Publishability / Confidence</div>
          <div class='kpi-value' style='color:{POSITIVE if snap.publishability_label == "Eligible" else WARNING if snap.publishability_label == "Review" else NEGATIVE};'>{snap.publishability_label}</div>
          <div class='kpi-sub'>{snap.confidence_label} \u00b7 {snap.confidence_score_pct:.0f}% confidence</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Spot / FV / Basis / Carry KPI strip ──────────────────────────────────
    st.markdown(f"""
    <div class='kpi-strip-wrap'>
      <div class='kpi-strip-ribbon'>ORIEL CPI BASIS \u00b7 Tier 1 \u00b7 Spot / Fair Value / Basis / Carry</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr))'>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Spot Index</div>
          <div class='kpi-value'>{snap.spot_index:.2f}</div>
          <div class='kpi-sub'>Front index level</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Fair Value ({int(fv_horizon)}d)</div>
          <div class='kpi-value kpi-value--lead'>{snap.fv_index:.4f}</div>
          <div class='kpi-sub'>Interpolated at horizon</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Simulated Perp</div>
          <div class='kpi-value' style='color:{basis_col};'>{snap.perp_price:.4f}</div>
          <div class='kpi-sub'>FV + basis</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Basis</div>
          <div class='kpi-value' style='color:{basis_col};'>{snap.basis_bp:+.1f} bp</div>
          <div class='kpi-sub'>Perp vs FV</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Ann. Carry</div>
          <div class='kpi-value' style='color:{carry_col};'>{snap.annualized_carry_bp:+.1f} bp</div>
          <div class='kpi-sub'>Spot to FV, ann.</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Main charts row ──────────────────────────────────────────────────────
    _ip_h = 318
    _dislo_h = 179
    _right_total = _ip_h + 8 + _dislo_h
    _left_overhead = 128
    _chart_h = _right_total - _left_overhead
    _bar_h   = _chart_h

    left, right = st.columns([2, 1], gap="medium", vertical_alignment="top")

    with left:
        st.markdown('<span class="oriel-main-split-left" aria-hidden="true"></span>', unsafe_allow_html=True)
        fig_curve = _make_perp_readiness_curve_chart(current_curve, prior_curve, int(fv_horizon), snap.fv_index, _chart_h)
        fig_bar   = _make_spot_fv_perp_bar(snap.spot_index, snap.fv_index, snap.perp_price, _bar_h)

        tab_t1_curve, tab_t1_bar = st.tabs(["Spot to Fair Value", "Spot vs FV vs Perp"])
        with tab_t1_curve:
            st.caption(f"Index level curve with FV horizon ({int(fv_horizon)}d) and prior-curve overlay.")
            st.plotly_chart(fig_curve, width="stretch", config=PLOTLY_CONFIG, key="t1_curve_chart")
        with tab_t1_bar:
            st.caption("Spot, interpolated fair value, and simulated perp price side by side.")
            st.plotly_chart(fig_bar, width="stretch", config=PLOTLY_CONFIG, key="t1_bar_chart")

    with right:
        st.markdown('<span class="oriel-main-split-right" aria-hidden="true"></span>', unsafe_allow_html=True)

        carry_dir = "\u2191" if snap.annualized_carry_bp >= 0 else "\u2193"
        basis_dir = "premium" if snap.basis_bp >= 0 else "discount"

        st.markdown(f"""
        <div class='ip-wrap'>
          <div class='ip-header'>
            <span class='ip-header-label'>Perp Print</span>
            <span class='ip-header-status' style='color:{POSITIVE};'>\u25cf Tier 1 Ready</span>
          </div>
          <div class='ip-highlight'>
            <span class='ip-hl-label'>Fair Value ({int(fv_horizon)}d horizon)</span>
            <span class='ip-hl-value'>{snap.fv_index:.4f}</span>
          </div>
          <div class='ip-body'>
            <div class='ip-row'><span class='ip-key'>Spot Index</span><span class='ip-val'>{snap.spot_index:.2f}</span></div>
            <div class='ip-row'><span class='ip-key'>Fair Value</span><span class='ip-val'>{snap.fv_index:.4f}</span></div>
            <div class='ip-row'><span class='ip-key'>Simulated Perp</span><span class='ip-val' style='color:{basis_col};'>{snap.perp_price:.4f}</span></div>
            <div class='ip-row'><span class='ip-key'>Basis</span><span class='ip-val' style='color:{basis_col};'>{snap.basis_bp:+.1f} bp ({basis_dir})</span></div>
            <div class='ip-row'><span class='ip-key'>Ann. Carry</span><span class='ip-val' style='color:{carry_col};'>{snap.annualized_carry_bp:+.1f} bp {carry_dir}</span></div>
            <div class='ip-row'><span class='ip-key'>FV Horizon</span><span class='ip-val'>{int(fv_horizon)} days</span></div>
            <div class='ip-row'><span class='ip-key'>Front CPI YoY</span><span class='ip-val'>{snap.front_expected_yoy_pct:.2f}%</span></div>
            <div class='ip-row'><span class='ip-key'>Curve Points</span><span class='ip-val'>{len(current_curve)}</span></div>
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class='dislo-wrap' style='margin-top:8px;'>
          <div class='dislo-header'><span class='dislo-title'>Perp Structure</span></div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Perp vs FV</span>
            <span class='dislo-val' style='color:{basis_col};'>{snap.basis_bp:+.1f} bp</span>
            <span class='dislo-signal' style='color:{basis_col};'>{basis_dir}</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Ann. Carry (spot\u2192FV)</span>
            <span class='dislo-val' style='color:{carry_col};'>{snap.annualized_carry_bp:+.1f} bp</span>
            <span class='dislo-signal' style='color:{carry_col};'>{carry_dir}</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Venue Target</span>
            <span class='dislo-val'>\u2014</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>Hyperliquid / AX</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Tier</span>
            <span class='dislo-val'>1</span>
            <span class='dislo-signal' style='color:{GOLD};'>Spot / FV / Carry</span>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div class='shdr oriel-section-gap'>Curve Construction / Microstructure / Confidence</div>", unsafe_allow_html=True)
    mc1, mc2, mc3 = st.columns(3, gap="medium")
    with mc1:
        st.markdown(f"""
        <div class='panel-card'>
          <div class='panel-title'>Explicit smoothing</div>
          <div class='panel-body'>
            <div><b>Requested:</b> liquidity-weighted monotone linear</div>
            <div><b>Used:</b> {smoothing_diag.method_used}</div>
            <div><b>Direction:</b> {smoothing_diag.monotone_direction}</div>
            <div><b>RMSE:</b> {smoothing_diag.rmse_bp:.1f} bp</div>
            <div><b>Max residual:</b> {smoothing_diag.max_residual_bp:.1f} bp</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with mc2:
        st.markdown(f"""
        <div class='panel-card'>
          <div class='panel-title'>Microstructure rules</div>
          <div class='panel-body'>
            <div><b>Proxy spread gate:</b> ≤ 35 bp</div>
            <div><b>Staleness gate:</b> ≤ 300s</div>
            <div><b>Selection waterfall:</b> tight+fresh mid → guarded mid → exclude</div>
            <div><b>Kalshi included:</b> {int(kalshi_constituents['included_in_curve'].sum())}/{len(kalshi_constituents)}</div>
            <div><b>ForecastEx included:</b> {int(forecastex_constituents['included_in_curve'].sum())}/{len(forecastex_constituents)}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with mc3:
        st.markdown(f"""
        <div class='panel-card'>
          <div class='panel-title'>Confidence gates</div>
          <div class='panel-body'>
            <div><b>Status:</b> {snap.publishability_label} · {snap.confidence_score_pct:.1f}%</div>
            <div><b>High threshold:</b> ≥ {conf_breakdown['high_threshold']:.0f}</div>
            <div><b>Review threshold:</b> ≥ {conf_breakdown['review_threshold']:.0f}</div>
            <div><b>Quality score:</b> {conf_breakdown['quality_score']:.1f}</div>
            <div><b>Freshness score:</b> {conf_breakdown['freshness_score']:.1f}</div>
            <div><b>Calibration score:</b> {conf_breakdown['calibration_score']:.1f}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div class='shdr oriel-section-gap'>Calibration / Trade Playbook</div>", unsafe_allow_html=True)
    cal_left, cal_right = st.columns([1.15, 1], gap="medium")
    with cal_left:
        st.markdown(f"""
        <div class='panel-card'>
          <div class='panel-title'>Weight calibration</div>
          <div class='panel-body'>
            <div><b>Rule:</b> {weight_calibration['calibration_rule']}</div>
            <div><b>Blend alpha:</b> {weight_calibration['blend_alpha']:.2f}</div>
            <div><b>Score share:</b> Kalshi {weight_calibration['score_weight_share_kalshi']:.2%} / ForecastEx {weight_calibration['score_weight_share_forecastex']:.2%}</div>
            <div><b>Effective share:</b> Kalshi {weight_calibration['effective_weight_share_kalshi']:.2%} / ForecastEx {weight_calibration['effective_weight_share_forecastex']:.2%}</div>
            <div><b>Historical calibration:</b> Kalshi {weight_calibration['kalshi_historical_calibration_score']:.1f} / ForecastEx {weight_calibration['forecastex_historical_calibration_score']:.1f}</div>
            <div><b>Weighted Brier:</b> Kalshi {weight_calibration['kalshi_weighted_mean_brier_score']:.3f} / ForecastEx {weight_calibration['forecastex_weighted_mean_brier_score']:.3f}</div>
            <div><b>Calibration sample:</b> Kalshi {weight_calibration['kalshi_calibration_sample_size']} / ForecastEx {weight_calibration['forecastex_calibration_sample_size']}</div>
            <div><b>Interpretation:</b> requested weights are preserved only when venue quality and historical calibration confirm them.</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(freshness_commentary)
    with cal_right:
        for idea in trade_ideas:
            st.markdown(f"""
            <div class='panel-card' style='margin-bottom:8px;'>
              <div class='panel-title'>{idea.title}</div>
              <div class='panel-body'>
                <div><b>Expression:</b> {idea.expression}</div>
                <div><b>Why now:</b> {idea.rationale}</div>
                <div><b>Trigger:</b> {idea.trigger}</div>
                <div><b>Risk:</b> {idea.risk_note}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Source Blend / Index Governance (2-column hardened) ─────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Source Blend / Index Governance</div>", unsafe_allow_html=True)
    _sb_left, _sb_right = st.columns([1.3, 1], gap="medium")
    with _sb_left:
        _wt_rows = []
        for _wd in [k_weight_diag, f_weight_diag]:
            _wt_rows.append({
                "Venue": _wd.venue,
                "Requested Wt": f"{_wd.requested_weight * 100:.0f}%",
                "Raw Score": f"{_wd.raw_venue_score:.1f}",
                "Raw Score Wt": f"{_wd.raw_score_weight * 100:.1f}%",
                "Effective Wt": f"{_wd.effective_weight * 100:.1f}%",
                "Eligible": "Yes" if _wd.eligible else "No",
                "Median Age": f"{_wd.median_quote_age_seconds:.0f}s" if _wd.median_quote_age_seconds is not None else "n/a",
                "Snapshot Span": f"{_wd.snapshot_span_seconds:.0f}s" if _wd.snapshot_span_seconds is not None else "n/a",
            })
        _wt_df = pd.DataFrame(_wt_rows)
        _wt_h = DESK_TABLE_HEADER_PX + len(_wt_df) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        _wt_fig = _plotly_desk_table(_wt_df, gold_column="Effective Wt")
        _wt_fig.update_layout(height=_wt_h)
        st.plotly_chart(_wt_fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="hardening_wt_tbl", height=_wt_h)

    with _sb_right:
        st.markdown(f"""
        <div class='dislo-wrap' style='margin-top:0;margin-bottom:0;'>
          <div class='dislo-header'><span class='dislo-title'>Index Governance</span></div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Weighting Rule</span>
            <span class='dislo-val'>Blend \u03b1 = 0.35</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>eff = \u03b1\u00b7req + (1-\u03b1)\u00b7score</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Eligibility Rule</span>
            <span class='dislo-val'>Kalshi {"Yes" if k_weight_diag.eligible else "No"} \u00b7 ForecastEx {"Yes" if f_weight_diag.eligible else "No"}</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'>Coverage + consistency gate</span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Freshness</span>
            <span class='dislo-val' style='font-size:0.68rem;'>{freshness_commentary[:80]}{"..." if len(freshness_commentary) > 80 else ""}</span>
            <span class='dislo-signal' style='color:{TEXT_MUTED};'></span>
          </div>
          <div class='dislo-row'>
            <span class='dislo-metric'>Methodology</span>
            <span class='dislo-val'>v0.1.0-tier1</span>
            <span class='dislo-signal' style='color:{GOLD};'>Governed blend</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Distribution / Confidence ────────────────────────────────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Distribution / Confidence</div>", unsafe_allow_html=True)
    _dc_left, _dc_right = st.columns([1.3, 1], gap="medium")
    with _dc_left:
        st.caption("Blended forward curve (see Spot to Fair Value chart above). Confidence bands planned for V2.")
        _fig_curve_mini = _make_perp_readiness_curve_chart(current_curve, prior_curve, int(fv_horizon), snap.fv_index, 280)
        st.plotly_chart(_fig_curve_mini, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="hardening_curve_mini")

    with _dc_right:
        _prob_rows = []
        for _rp in blended_ref_pts:
            _probs = _rp.blended_threshold_probs or {}
            _disp = 0.0
            if _rp.source_residual_bp:
                _disp = max(abs(v) for v in _rp.source_residual_bp.values())
            _prob_rows.append({
                "Horizon": f"{_rp.horizon_months:.1f}M",
                "P(>2.0%)": f"{_probs.get('gt_2_0', 0.0) * 100:.1f}%",
                "P(>2.5%)": f"{_probs.get('gt_2_5', 0.0) * 100:.1f}%",
                "P(>3.0%)": f"{_probs.get('gt_3_0', 0.0) * 100:.1f}%",
                "Std Dev": f"{_rp.blended_std_dev_pct:.2f}%" if _rp.blended_std_dev_pct else "n/a",
                "Dispersion": f"{_disp:.1f} bp",
                "Conf Score": f"{_rp.distribution_confidence_score:.1f}",
            })
        _prob_df = pd.DataFrame(_prob_rows)
        _prob_h = DESK_TABLE_HEADER_PX + len(_prob_df) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
        _prob_fig = _plotly_desk_table(_prob_df, gold_column="Conf Score")
        _prob_fig.update_layout(height=_prob_h)
        st.plotly_chart(_prob_fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="hardening_prob_tbl", height=_prob_h)

    # ── Timestamp / Freshness Diagnostics ────────────────────────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Timestamp / Freshness Diagnostics</div>", unsafe_allow_html=True)
    _fresh_rows = []
    for _vf in [k_freshness, f_freshness]:
        _cross_gap = blended_freshness.cross_venue_median_age_gap_seconds
        _comment = ""
        if _vf.median_quote_age_seconds <= 30:
            _comment = "Fresh"
        elif _vf.median_quote_age_seconds <= 60:
            _comment = "Aging"
        else:
            _comment = "Stale"
        _fresh_rows.append({
            "Venue": _vf.venue,
            "Median Age": f"{_vf.median_quote_age_seconds:.0f}s",
            "Max Age": f"{_vf.max_quote_age_seconds:.0f}s",
            "Fresh %": f"{_vf.fresh_quote_fraction * 100:.0f}%",
            "Stale %": f"{_vf.stale_quote_fraction * 100:.0f}%",
            "Snapshot Span": f"{_vf.snapshot_span_seconds:.0f}s",
            "Cross-Venue Gap": f"{_cross_gap:.0f}s",
            "Comment": _comment,
        })
    _fresh_df = pd.DataFrame(_fresh_rows)
    _fresh_h = DESK_TABLE_HEADER_PX + len(_fresh_df) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    _fresh_fig = _plotly_desk_table(_fresh_df, gold_column="Median Age")
    _fresh_fig.update_layout(height=_fresh_h)
    st.plotly_chart(_fresh_fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="hardening_fresh_tbl", height=_fresh_h)

    st.markdown(
        f"<div class='note-box' style='margin-top:4px;font-size:0.71rem'>"
        f"<strong>Freshness commentary:</strong> {freshness_commentary}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Venue Diagnostics ────────────────────────────────────────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Venue Diagnostics</div>", unsafe_allow_html=True)
    _render_basis_diagnostics(diag_bundle)

    # ── Pricing table ────────────────────────────────────────────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Pricing Table</div>", unsafe_allow_html=True)

    tbl_df = current_curve.copy()
    tbl_df["fv_marker"] = tbl_df["days_from_valuation"].apply(
        lambda d: "\u25c0 FV Horizon" if int(fv_horizon) == d else (
            "\u2190 nearest" if abs(int(fv_horizon) - d) == tbl_df["days_from_valuation"].sub(int(fv_horizon)).abs().min() else ""
        )
    )
    tbl_df["target_month"] = tbl_df["target_month"].dt.strftime("%Y-%m")
    tbl_display = tbl_df.rename(columns={
        "target_month": "Target Month",
        "days_from_valuation": "Days",
        "expected_yoy_pct": "Expected YoY (%)",
        "index_level": "Index Level",
        "std_dev_pct": "Std Dev (%)",
        "kalshi_weight": "Kalshi Wt",
        "forecastex_weight": "ForecastEx Wt",
        "fv_marker": "FV Marker",
    })
    _tbl_h = DESK_TABLE_HEADER_PX + len(tbl_display) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    _fig_tbl = _plotly_desk_table(tbl_display)
    _fig_tbl.update_layout(height=_tbl_h)
    st.plotly_chart(_fig_tbl, width="stretch", config=PLOTLY_CONFIG, theme=None, key="t1_pricing_tbl", height=_tbl_h)

    st.markdown(
        f"<div style='padding:6px 0 2px;font-size:0.68rem;color:{TEXT_MUTED};'>"
        f"Tier 1 only: FV interpolation, spot/FV/perp comparison, prior-curve overlay, basis and carry. "
        f"Tier 2+ (funding, liquidation, matching engine) not included in this layer.</div>",
        unsafe_allow_html=True,
    )
