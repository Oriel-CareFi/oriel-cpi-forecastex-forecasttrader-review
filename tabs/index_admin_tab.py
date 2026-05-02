from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.index_admin import load_index_admin_bundle
from ui.charts import _layout, _xaxis, _yaxis
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import _plotly_desk_table
from ui.tokens import (
    BG_ELEVATED, DESK_TABLE_HEADER_PX, DESK_TABLE_PAD_PX, DESK_TABLE_ROW_PX,
    GOLD, NEGATIVE, POSITIVE, SERIES2, SERIES_MUTE,
    TEXT_MUTED, TEXT_SEC, WARNING,
)


def _decision_color(decision: str) -> str:
    return {"publish": POSITIVE, "restricted": WARNING, "hold": NEGATIVE}.get(decision, TEXT_MUTED)


# ── Charts ────────────────────────────────────────────────────────────────────

def _line_chart(outputs_df: pd.DataFrame) -> go.Figure:
    x = outputs_df["target_month"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=outputs_df["observed_market_implied"],
        mode="lines+markers", name="Market-Implied Curve",
        line=dict(color=SERIES_MUTE, width=1.8, dash="dash"),
        marker=dict(size=5, color=SERIES_MUTE),
        hovertemplate="%{x} \u00b7 Market: %{y:.4f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=outputs_df["blended_reference"],
        mode="lines+markers", name="Blended Reference",
        line=dict(color=GOLD, width=2.4),
        marker=dict(size=7, color=GOLD, line=dict(color=BG_ELEVATED, width=1.5)),
        hovertemplate="%{x} \u00b7 Reference: %{y:.4f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=outputs_df["fair_value"],
        mode="lines+markers", name="Fair Value",
        line=dict(color=SERIES2, width=1.6),
        marker=dict(size=5, color=SERIES2),
        hovertemplate="%{x} \u00b7 FV: %{y:.4f}<extra></extra>",
    ))
    fig.update_layout(**_layout(
        height=310,
        xaxis=_xaxis(title=None),
        yaxis=_yaxis(title="Implied CPI YoY"),
    ))
    return fig


def _weight_chart(obs_df: pd.DataFrame) -> go.Figure:
    grouped = (
        obs_df[obs_df["is_eligible"]]
        .pivot_table(index="target_month", columns="venue", values="weight", aggfunc="sum", fill_value=0.0)
        .reset_index()
    )
    venue_colors = [GOLD, SERIES2, POSITIVE, SERIES_MUTE]
    fig = go.Figure()
    for i, venue in enumerate([c for c in grouped.columns if c != "target_month"]):
        fig.add_trace(go.Bar(
            x=grouped["target_month"], y=grouped[venue],
            name=venue.title(),
            marker_color=venue_colors[i % len(venue_colors)],
            hovertemplate=f"{venue.title()}: %{{y:.3f}}<extra></extra>",
        ))
    fig.update_layout(**_layout(
        barmode="stack", height=310,
        xaxis=_xaxis(title=None),
        yaxis=_yaxis(title="Weight"),
    ))
    return fig


def _publishability_bar(quality_df: pd.DataFrame) -> go.Figure:
    colors = [_decision_color(d) for d in quality_df["publication_decision"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=quality_df["target_month"], y=quality_df["publishability_score"],
        marker_color=colors,
        text=[f"{s:.2f}" for s in quality_df["publishability_score"]],
        textposition="outside",
        textfont=dict(size=10, color=TEXT_SEC),
        hovertemplate="%{x}<br>Score: %{y:.3f}<extra></extra>",
    ))
    fig.add_hline(y=0.80, line_color=POSITIVE, line_dash="dot", line_width=1)
    fig.add_hline(y=0.65, line_color=WARNING, line_dash="dot", line_width=1)
    fig.update_layout(**_layout(
        height=310,
        xaxis=_xaxis(title=None),
        yaxis=_yaxis(title="Score", range=[0, 1.1]),
    ))
    return fig


_VIEWPORT_ROWS = 6  # tables taller than this get a scrollable container


def _desk(df: pd.DataFrame, gold_column: str | None = None,
          flagged: set[int] | None = None) -> tuple[go.Figure, int]:
    """
    Build a desk table sized to fit ALL its rows. Returns (fig, viewport_h):
    viewport_h caps at 6 rows so larger tables get a scrollable container in
    the calling site (st.container(height=viewport_h)).
    """
    n = len(df)
    content_h = DESK_TABLE_HEADER_PX + n * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    cap_h = DESK_TABLE_HEADER_PX + _VIEWPORT_ROWS * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    viewport_h = min(content_h, cap_h)
    fig = _plotly_desk_table(df, gold_column=gold_column, flagged_rows=flagged)
    fig.update_layout(height=content_h)
    return fig, viewport_h


def _fmt4(x) -> str:
    return f"{x:.4f}"

def _fmt1(x) -> str:
    return f"{x:,.1f}"


# ── Renderer ─────────────────────────────────────────────────────────────────

def render_index_admin_tab() -> None:
    bundle = load_index_admin_bundle()
    definition  = bundle["definition"]
    obs_df      = bundle["observations_df"].copy()
    quality_df  = bundle["quality_df"].copy()
    outputs_df  = bundle["outputs_df"].copy()
    runs_df     = bundle["runs_df"].copy()
    fallback_df = bundle["fallback_df"].copy()
    record      = bundle["publication_record"]

    # ── Title (left) + inline selectors (right) — all on one horizontal line ──
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    hcl, idx_lbl, idx_dt, run_lbl, run_dt, exp_col = st.columns(
        [2.4, 0.45, 1.55, 0.7, 1.55, 1.0], gap="small", vertical_alignment="center"
    )
    with hcl:
        st.markdown(f"""
        <div class='oriel-page-head'>
          <span class='oriel-page-title'>Index Administrator</span>
          <span class='version-chip'>{definition.methodology_version}</span>
          <span class='version-chip' style='background:#1b2a3e;color:#7aa2f7;border-color:#2e4a72;'>{definition.index_id}</span>
        </div>""", unsafe_allow_html=True)
    with idx_lbl:
        st.markdown("<div class='ctrl-vd-label' style='text-align:right;margin-bottom:0;'>Index</div>", unsafe_allow_html=True)
    with idx_dt:
        st.selectbox("Index", [definition.index_id], index=0,
                     key="index_admin_selector", label_visibility="collapsed")
    with run_lbl:
        st.markdown("<div class='ctrl-vd-label' style='text-align:right;margin-bottom:0;'>As-of Run</div>", unsafe_allow_html=True)
    with run_dt:
        st.selectbox("As-of Run", runs_df["run_id"].tolist(), index=0,
                     key="index_admin_run_selector", label_visibility="collapsed")
    with exp_col:
        st.download_button(
            "\u2193 Export run",
            data=outputs_df.to_csv(index=False).encode("utf-8"),
            file_name="index_admin_latest_run.csv",
            mime="text/csv",
        )

    st.markdown(
        "<div style='font-size:0.75rem;color:#8fa3b8;margin:4px 0 10px;'>"
        "Governed reference construction, publication controls, and audit traceability.</div>",
        unsafe_allow_html=True,
    )

    # ── Top KPI strip ─────────────────────────────────────────────────────────
    pub_status_color = POSITIVE if record.publication_status == "published" else WARNING
    avg_pub     = quality_df["publishability_score"].mean()
    avg_pub_col = POSITIVE if avg_pub >= 0.80 else WARNING if avg_pub >= 0.65 else NEGATIVE
    pub_n       = len(record.published_buckets)
    total_n     = len(outputs_df)
    bucket_col  = POSITIVE if pub_n == total_n else WARNING if pub_n > 0 else NEGATIVE

    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-bottom:10px'>
      <div class='kpi-strip-ribbon'>ORIEL CPI BLENDED REFERENCE INDEX \u00b7 Governed blend \u00b7 Kalshi + ForecastEx</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr))'>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Methodology</div>
          <div class='kpi-value'>{definition.methodology_version}</div>
          <div class='kpi-sub'>{definition.publication_cadence} \u00b7 {definition.domain}</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Publication Status</div>
          <div class='kpi-value' style='color:{pub_status_color};font-size:0.84rem;'>{record.publication_status}</div>
          <div class='kpi-sub'>As of {record.as_of[:10]}</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Published Buckets</div>
          <div class='kpi-value kpi-value--lead' style='color:{bucket_col};'>{pub_n} / {total_n}</div>
          <div class='kpi-sub'>{len(record.held_buckets)} held</div>
        </div>
        <div class='kpi-cell'>
          <div class='kpi-micro'>Avg Publishability</div>
          <div class='kpi-value kpi-value--lead' style='color:{avg_pub_col};'>{avg_pub:.2f}</div>
          <div class='kpi-sub'>Across {total_n} buckets</div>
        </div>
        <div class='kpi-cell kpi-cell--pub'>
          <div class='kpi-micro'>Latest Run</div>
          <div class='kpi-value kpi-pub-val kpi-pub--ok' style='font-size:0.78rem;'>{record.as_of.replace("T"," ")[:16]} UTC</div>
          <div class='kpi-sub'>{record.run_id}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Inner tabs ────────────────────────────────────────────────────────────
    tab_def, tab_inputs, tab_calc, tab_pub, tab_audit = st.tabs([
        "Index Definition",
        "Eligibility & Inputs",
        "Calculation Engine",
        "Publication Controls",
        "Audit Trail",
    ])

    # ── INDEX DEFINITION ─────────────────────────────────────────────────────
    with tab_def:
        left, right = st.columns([1.1, 1.5], gap="medium")

        with left:
            st.markdown("<div class='shdr'>Benchmark Overview</div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='dislo-wrap'>
              <div class='dislo-row'><span class='dislo-metric'>Index ID</span><span class='dislo-val'>{definition.index_id}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{definition.domain}</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Name</span><span class='dislo-val' style='font-size:0.70rem;'>{definition.index_name}</span><span class='dislo-signal'></span></div>
              <div class='dislo-row'><span class='dislo-metric'>Status</span><span class='dislo-val' style='color:{POSITIVE};'>{definition.status}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>since {definition.effective_date}</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Currency</span><span class='dislo-val'>{definition.currency}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{definition.timezone}</span></div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div class='shdr oriel-section-gap'>Maturity Coverage</div>", unsafe_allow_html=True)
            bkt_df = outputs_df[["target_month", "publishability_score", "fallback_used"]].copy()
            bkt_df.columns = ["Month", "Pub Score", "Fallback"]
            bkt_df["Pub Score"] = bkt_df["Pub Score"].map(_fmt4)
            bkt_df["Fallback"] = bkt_df["Fallback"].map(lambda x: "Yes" if x else "No")
            _f, _h = _desk(bkt_df, gold_column="Pub Score")
            with st.container(height=_h, border=False, key="scroll_def_bkt"):
                st.plotly_chart(_f, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="def_bkt")

        with right:
            st.markdown("<div class='shdr'>Methodology Metadata</div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='dislo-wrap'>
              <div class='dislo-row'><span class='dislo-metric'>Methodology Version</span><span class='dislo-val'>{definition.methodology_version}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{definition.effective_date}</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Publication Cadence</span><span class='dislo-val'>{definition.publication_cadence}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'></span></div>
              <div class='dislo-row'><span class='dislo-metric'>Refresh Cadence</span><span class='dislo-val'>{definition.refresh_cadence_seconds}s</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>real-time</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Timezone</span><span class='dislo-val'>{definition.timezone}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'></span></div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div class='shdr oriel-section-gap'>Methodology Summary</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='note-box'>{definition.description}<br><br>"
                f"<span style='color:{TEXT_MUTED};font-size:0.68rem;'>"
                "Market-Implied Curve: normalized eligible market observations. "
                "Blended Reference Index: governed published output. "
                "Fair Value Curve: model-informed pricing layer."
                "</span></div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div class='shdr oriel-section-gap'>Publication Record</div>", unsafe_allow_html=True)
            _pub_str  = ", ".join(record.published_buckets) or "\u2014"
            _held_str = ", ".join(record.held_buckets) or "\u2014"
            st.markdown(f"""
            <div class='dislo-wrap'>
              <div class='dislo-row'><span class='dislo-metric'>Status</span><span class='dislo-val' style='color:{pub_status_color};'>{record.publication_status}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{record.run_id}</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Published</span><span class='dislo-val' style='color:{POSITIVE};'>{_pub_str}</span><span class='dislo-signal'></span></div>
              <div class='dislo-row'><span class='dislo-metric'>Held</span><span class='dislo-val' style='color:{NEGATIVE};'>{_held_str}</span><span class='dislo-signal'></span></div>
            </div>
            """, unsafe_allow_html=True)

    # ── ELIGIBILITY & INPUTS ──────────────────────────────────────────────────
    with tab_inputs:
        fc1, fc2, fc3, _ = st.columns([1.2, 1.2, 0.8, 2.0], gap="small", vertical_alignment="bottom")
        months = ["All"] + sorted(obs_df["target_month"].unique().tolist())
        venues = ["All"] + sorted(obs_df["venue"].unique().tolist())
        with fc1:
            st.markdown("<div class='ctrl-vd-label'>Target Month</div>", unsafe_allow_html=True)
            selected_month = st.selectbox("Target month", months, key="idx_admin_month_filter", label_visibility="collapsed")
        with fc2:
            st.markdown("<div class='ctrl-vd-label'>Venue</div>", unsafe_allow_html=True)
            selected_venue = st.selectbox("Venue", venues, key="idx_admin_venue_filter", label_visibility="collapsed")
        with fc3:
            st.markdown("<div class='ctrl-vd-label' style='margin-bottom:6px;'>&nbsp;</div>", unsafe_allow_html=True)
            eligible_only = st.toggle("Eligible only", value=False, key="idx_admin_eligible_only")

        filtered = obs_df.copy()
        if selected_month != "All":
            filtered = filtered[filtered["target_month"] == selected_month]
        if selected_venue != "All":
            filtered = filtered[filtered["venue"] == selected_venue]
        if eligible_only:
            filtered = filtered[filtered["is_eligible"]]

        show_cols = ["target_month", "venue", "instrument_id", "implied_value", "bid", "ask",
                     "spread_bps", "depth", "open_interest", "source_timestamp", "age_seconds",
                     "weight", "is_eligible", "exclusion_reason"]
        _inp = filtered[show_cols].copy()
        # Shorten timestamp: "2026-04-13T10:30:24+00:00" -> "2026-04-13 10:30:24"
        _inp["source_timestamp"] = _inp["source_timestamp"].astype(str).str[:19].str.replace("T", " ", regex=False)
        for _c in ["implied_value", "bid", "ask", "weight"]:
            _inp[_c] = _inp[_c].map(_fmt4)
        for _c in ["spread_bps", "depth", "open_interest"]:
            _inp[_c] = _inp[_c].map(_fmt1)
        _inp["is_eligible"] = _inp["is_eligible"].map(lambda x: "Yes" if x else "No")
        _inp["exclusion_reason"] = _inp["exclusion_reason"].fillna("\u2014")
        _flagged = {i for i, v in enumerate(_inp["is_eligible"].tolist()) if v == "No"}
        _f, _h = _desk(_inp, gold_column="weight", flagged=_flagged)
        with st.container(height=_h, border=False, key="scroll_inp_tbl"):
            st.plotly_chart(_f, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="inp_tbl")
        st.markdown(
            f"<div style='font-size:0.68rem;color:{TEXT_MUTED};margin-top:4px;'>"
            "Flagged rows are ineligible observations. Timestamps and exclusion reasons surfaced for market-maker diligence.</div>",
            unsafe_allow_html=True,
        )

    # ── CALCULATION ENGINE ────────────────────────────────────────────────────
    with tab_calc:
        bars_col, line_col = st.columns([1.0, 1.15], gap="medium")
        with bars_col:
            bar_wt, bar_pub = st.tabs([
                "Venue Weight Distribution",
                "Publishability Score",
            ])
            with bar_wt:
                st.plotly_chart(_weight_chart(obs_df), use_container_width=True,
                                config=PLOTLY_CONFIG, theme=None, key="calc_wt")
            with bar_pub:
                st.plotly_chart(_publishability_bar(quality_df), use_container_width=True,
                                config=PLOTLY_CONFIG, theme=None, key="calc_pub_bar")
        with line_col:
            st.markdown("<div class='shdr'>Curve Comparison \u00b7 Market-Implied vs Blended vs Fair Value</div>", unsafe_allow_html=True)
            st.plotly_chart(_line_chart(outputs_df), use_container_width=True,
                            config=PLOTLY_CONFIG, theme=None, key="calc_line")

        st.markdown("<div class='shdr oriel-section-gap'>Calculation Output</div>", unsafe_allow_html=True)
        calc = outputs_df.merge(quality_df[["target_month", "publication_decision"]], on="target_month", how="left")[[
            "target_month", "observed_market_implied", "blended_reference", "fair_value",
            "top_weighted_source", "fallback_used", "fallback_level",
            "publishability_score", "publication_decision",
        ]].copy()
        calc["observed_market_implied"] = calc["observed_market_implied"].map(_fmt4)
        calc["blended_reference"]       = calc["blended_reference"].map(_fmt4)
        calc["fair_value"]              = calc["fair_value"].map(_fmt4)
        calc["publishability_score"]    = calc["publishability_score"].map(_fmt4)
        calc["fallback_used"]           = calc["fallback_used"].map(lambda x: "Yes" if x else "No")
        calc["fallback_level"]          = calc["fallback_level"].fillna("\u2014")
        calc["top_weighted_source"]     = calc["top_weighted_source"].fillna("\u2014")
        _f, _h = _desk(calc, gold_column="blended_reference")
        with st.container(height=_h, border=False, key="scroll_calc_tbl"):
            st.plotly_chart(_f, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="calc_tbl")

    # ── PUBLICATION CONTROLS ──────────────────────────────────────────────────
    with tab_pub:
        publish_ct    = int((quality_df["publication_decision"] == "publish").sum())
        restricted_ct = int((quality_df["publication_decision"] == "restricted").sum())
        hold_ct       = int((quality_df["publication_decision"] == "hold").sum())
        avg_ts  = quality_df["timestamp_integrity_score"].mean()
        avg_div = quality_df["source_diversity_score"].mean()

        st.markdown(f"""
        <div class='kpi-strip-wrap' style='margin-bottom:10px'>
          <div class='kpi-strip-ribbon'>PUBLICATION SUMMARY \u00b7 Decision breakdown \u00b7 Governed quality thresholds</div>
          <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr))'>
            <div class='kpi-cell'><div class='kpi-micro'>Publish</div>
              <div class='kpi-value kpi-value--lead' style='color:{POSITIVE};'>{publish_ct}</div>
              <div class='kpi-sub'>Score \u2265 0.80</div></div>
            <div class='kpi-cell'><div class='kpi-micro'>Restricted</div>
              <div class='kpi-value kpi-value--lead' style='color:{WARNING};'>{restricted_ct}</div>
              <div class='kpi-sub'>Score 0.65\u20130.80</div></div>
            <div class='kpi-cell'><div class='kpi-micro'>Hold</div>
              <div class='kpi-value kpi-value--lead' style='color:{NEGATIVE};'>{hold_ct}</div>
              <div class='kpi-sub'>Score &lt; 0.65</div></div>
            <div class='kpi-cell'><div class='kpi-micro'>Avg Timestamp Integrity</div>
              <div class='kpi-value' style='color:{POSITIVE if avg_ts >= 0.8 else WARNING};'>{avg_ts:.2f}</div>
              <div class='kpi-sub'>Quote age freshness</div></div>
            <div class='kpi-cell'><div class='kpi-micro'>Avg Source Diversity</div>
              <div class='kpi-value' style='color:{POSITIVE if avg_div >= 0.75 else WARNING};'>{avg_div:.2f}</div>
              <div class='kpi-sub'>Venue concentration</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        left_pub, right_pub = st.columns([2.2, 1.0], gap="medium")
        with left_pub:
            st.markdown("<div class='shdr'>Quality Score Breakdown by Bucket</div>", unsafe_allow_html=True)
            pub_df = quality_df.merge(outputs_df[["target_month", "reason_codes"]], on="target_month", how="left").copy()
            pub_df["reason_codes"] = pub_df["reason_codes"].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")
            pub_cols = ["target_month", "quality_score", "timestamp_integrity_score",
                        "source_diversity_score", "continuity_score",
                        "fallback_penalty_adjusted_score", "publishability_score",
                        "publication_decision", "reason_codes"]
            pub_d = pub_df[pub_cols].copy()
            for _c in ["quality_score", "timestamp_integrity_score", "source_diversity_score",
                       "continuity_score", "fallback_penalty_adjusted_score", "publishability_score"]:
                pub_d[_c] = pub_d[_c].map(_fmt4)
            _flagged_pub = {i for i, d in enumerate(pub_df["publication_decision"].tolist()) if d == "hold"}
            _f, _h = _desk(pub_d, gold_column="publishability_score", flagged=_flagged_pub)
            with st.container(height=_h, border=False, key="scroll_pub_tbl"):
                st.plotly_chart(_f, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="pub_tbl")
            st.markdown(
                f"<div style='font-size:0.68rem;color:{TEXT_MUTED};margin-top:4px;'>"
                "Quality (20%) + timestamp integrity (20%) + source diversity (20%) + fallback penalty (15%) + continuity (15%) + other (10%).</div>",
                unsafe_allow_html=True,
            )

        with right_pub:
            st.markdown("<div class='shdr'>Decision Thresholds</div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='dislo-wrap'>
              <div class='dislo-row'><span class='dislo-metric'>Publish</span><span class='dislo-val' style='color:{POSITIVE};'>score \u2265 0.80</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>full publication</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Restricted</span><span class='dislo-val' style='color:{WARNING};'>0.65\u20130.80</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>diagnostic only</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Hold</span><span class='dislo-val' style='color:{NEGATIVE};'>score &lt; 0.65</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>withheld</span></div>
            </div>
            <div class='shdr oriel-section-gap'>Override Status</div>
            <div class='dislo-wrap'>
              <div class='dislo-row'><span class='dislo-metric'>Override Applied</span><span class='dislo-val'>{record.override_applied}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'></span></div>
              <div class='dislo-row'><span class='dislo-metric'>Override Note</span><span class='dislo-val'>{record.override_note or "none"}</span><span class='dislo-signal'></span></div>
            </div>
            """, unsafe_allow_html=True)

    # ── AUDIT TRAIL ───────────────────────────────────────────────────────────
    with tab_audit:
        st.markdown("<div class='shdr'>Run History</div>", unsafe_allow_html=True)
        runs_d = runs_df.copy()
        for _c in ["published_buckets", "held_buckets", "restricted_buckets", "fallback_count"]:
            if _c in runs_d.columns:
                runs_d[_c] = runs_d[_c].astype(str)
        _f, _h = _desk(runs_d, gold_column="published_buckets")
        with st.container(height=_h, border=False, key="scroll_audit_runs"):
            st.plotly_chart(_f, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="audit_runs")

        al, ar = st.columns([1.4, 1.0], gap="medium")
        with al:
            st.markdown("<div class='shdr oriel-section-gap'>Fallback Hierarchy Usage</div>", unsafe_allow_html=True)
            _f, _h = _desk(fallback_df, gold_column="fallback_level")
            with st.container(height=_h, border=False, key="scroll_audit_fb"):
                st.plotly_chart(_f, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="audit_fb")
        with ar:
            st.markdown("<div class='shdr oriel-section-gap'>Latest Publication Record</div>", unsafe_allow_html=True)
            _pub_str  = ", ".join(record.published_buckets) or "\u2014"
            _held_str = ", ".join(record.held_buckets) or "\u2014"
            _ts_str   = record.created_at[:19].replace("T", " ") + " UTC"
            _override_val = "Yes" if record.override_applied else "No"
            _override_signal = record.override_note or "\u2014"
            st.markdown(f"""
            <div class='dislo-wrap'>
              <div class='dislo-row'><span class='dislo-metric'>Run ID</span><span class='dislo-val'>{record.run_id}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{_ts_str}</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Index</span><span class='dislo-val'>{record.index_id}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{definition.methodology_version}</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Status</span><span class='dislo-val' style='color:{pub_status_color};'>{record.publication_status}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>governed</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Published</span><span class='dislo-val' style='color:{POSITIVE};'>{_pub_str}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{len(record.published_buckets)} bucket(s)</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Held</span><span class='dislo-val' style='color:{NEGATIVE};'>{_held_str}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{len(record.held_buckets)} bucket(s)</span></div>
              <div class='dislo-row'><span class='dislo-metric'>Override</span><span class='dislo-val'>{_override_val}</span><span class='dislo-signal' style='color:{TEXT_MUTED};'>{_override_signal}</span></div>
            </div>
            """, unsafe_allow_html=True)
