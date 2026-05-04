"""
tabs/review_overview_tab.py

External-facing overview for the ForecastEx / ForecastTrader CPI review build.

This replaces internal talking-point panels such as Audience Lens, 5–7 Minute
Walkthrough, and Close / Ask with a product-oriented App Overview and tab guide.
"""
from __future__ import annotations

import streamlit as st


def render_review_overview_tab() -> None:
    """Render the external-facing CPI review-build overview."""
    st.markdown(
        """
        <div class="review-overview-hero">
          <div class="review-eyebrow">ForecastTrader Review Build</div>
          <h1>Oriel CPI Review Build</h1>
          <p>
            This review build shows how Oriel translates listed forecast-contract signals
            into continuous, institution-usable reference surfaces and trading workflows.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### What this review build demonstrates")
    st.markdown(
        """
        <div class="review-grid review-grid-2">
          <div class="review-card">
            <div class="review-card-title">1 · Listed CPI contracts can become a curve</div>
            <div class="review-card-body">
              ForecastEx-style binary thresholds can be normalized, aligned by maturity,
              and stitched into a forward CPI surface that institutions can reference.
            </div>
          </div>
          <div class="review-card">
            <div class="review-card-title">2 · A curve is only useful if it is benchmarkable</div>
            <div class="review-card-body">
              Cross-venue diagnostics, confidence scoring, liquidity, quote freshness,
              calibration, and parity checks turn the surface into a relative-value workflow.
            </div>
          </div>
          <div class="review-card">
            <div class="review-card-title">3 · The same workflow extends to medical inflation</div>
            <div class="review-card-body">
              Public BLS medical-CPI components can anchor a healthcare reference framework
              and support illustrative ForecastEx-style basis-contract design.
            </div>
          </div>
          <div class="review-card">
            <div class="review-card-title">4 · The first healthcare hedge is medical CPI vs. CPI</div>
            <div class="review-card-body">
              The initial trade is a spread every payer, provider, employer, and reinsurer
              already lives with — medical inflation relative to headline CPI.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Tab overview")
    st.markdown(
        """
        <div class="review-tab-list">
          <div class="review-tab-row">
            <div class="review-tab-name">App Overview</div>
            <div class="review-tab-desc">Frames the review build and explains how to read the workflow.</div>
          </div>
          <div class="review-tab-row">
            <div class="review-tab-name">Oriel CPI Forward Index · Kalshi-style</div>
            <div class="review-tab-desc">Shows CPI threshold and exact-outcome contracts translated into an implied CPI forward reference.</div>
          </div>
          <div class="review-tab-row">
            <div class="review-tab-name">Oriel CPI Forward Index · ForecastEx-style</div>
            <div class="review-tab-desc">Shows how ForecastEx-style CPI inputs can be normalized into common maturities, thresholds, and implied forward values.</div>
          </div>
          <div class="review-tab-row">
            <div class="review-tab-name">Oriel CPI Forward Index · Polymarket-style</div>
            <div class="review-tab-desc">Demonstrates how a second event-contract venue can be standardized into the same reference framework.</div>
          </div>
          <div class="review-tab-row">
            <div class="review-tab-name">Oriel CPI Basis</div>
            <div class="review-tab-desc">Compares market-implied CPI levels against Oriel fair value, including dislocation, confidence, liquidity, and calibration indicators.</div>
          </div>
          <div class="review-tab-row">
            <div class="review-tab-name">Medical CPI Tracker</div>
            <div class="review-tab-desc">Extends the reference framework into healthcare inflation using public BLS medical CPI components and healthcare-specific inflation signals.</div>
          </div>
          <div class="review-tab-row">
            <div class="review-tab-name">ForecastEx Medical Basis</div>
            <div class="review-tab-desc">Illustrates a potential medical-inflation-versus-CPI basis contract, including spread thresholds, settlement logic, and implied basis-market outputs.</div>
          </div>
          <div class="review-tab-row">
            <div class="review-tab-name">OTC Parity Validation</div>
            <div class="review-tab-desc">Shows how Oriel reference outputs can be compared against external benchmark markets and parity checks to support institutional validation.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Purpose")
    st.markdown(
        """
        <div class="review-purpose-card">
          The goal is to show how ForecastEx / ForecastTrader-listed contracts could serve
          as source markets for broader reference, analytics, and execution-intelligence
          workflows — with CPI as the initial proof point and healthcare inflation as the
          differentiated expansion path.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Illustrative review build only. Figures, reference levels, and contract specifications are sample outputs unless explicitly marked as live."
    )
