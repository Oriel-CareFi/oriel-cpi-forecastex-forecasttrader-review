"""
services/review_password_gate.py — App-level password gate for the
ForecastTrader external-review deployment.

Per Chris's password-gated handoff
(docs/deployments/forecasttrader_password_gated_review_deployment.md):
the deployment is a *public* Streamlit app gated by an in-app password
stored in Streamlit Secrets as ``review_password``. This is the
workaround for Streamlit Community Cloud's one-private-app-per-workspace
limit — the production private app stays untouched.

The gate is enabled when the Streamlit secret ``REVIEW_BUILD`` is set
to ``"true"``. That keeps the same code safely mergeable back to
``main``: production deployments without the secret remain ungated.

The password comparison uses :func:`hmac.compare_digest` to avoid
leaking timing information.
"""
from __future__ import annotations

import hmac

import streamlit as st


def check_review_password() -> bool:
    """Return True iff a valid review password is in session state.

    Renders the password prompt UI as a side effect when not yet
    authenticated. Caller is expected to call ``st.stop()`` when this
    returns False so no review-only content renders.
    """

    def _password_entered() -> None:
        entered = st.session_state.get("review_password_input", "")
        try:
            expected = st.secrets.get("review_password", "")
        except Exception:
            expected = ""
        if expected and hmac.compare_digest(str(entered), str(expected)):
            st.session_state["review_password_correct"] = True
            # Don't keep the typed password in session state.
            del st.session_state["review_password_input"]
        else:
            st.session_state["review_password_correct"] = False

    if st.session_state.get("review_password_correct", False):
        return True

    # ── Gate UI ───────────────────────────────────────────────────────────────
    st.title("Oriel CPI Demo")
    st.caption("ForecastTrader review build")

    st.text_input(
        "Review password",
        type="password",
        on_change=_password_entered,
        key="review_password_input",
    )

    if "review_password_correct" in st.session_state:
        st.error("Password incorrect.")

    return False


def review_build_gate_enabled() -> bool:
    """Return True iff the password gate should be active for this deploy.

    Reads the ``REVIEW_BUILD`` value from Streamlit Secrets (per Chris's
    handoff Step 3). Defaults to False so production deployments without
    the secret stay open.
    """
    try:
        value = st.secrets.get("REVIEW_BUILD", "false")
    except Exception:
        value = "false"
    return str(value).strip().lower() == "true"
