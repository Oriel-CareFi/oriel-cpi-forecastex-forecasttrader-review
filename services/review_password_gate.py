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

The gate UI is intentionally minimal — vertically centered app name,
subtitle, and password input. No card, no logo, no footer. Lets the
reviewer focus on the one thing they need to do.
"""
from __future__ import annotations

import hmac

import streamlit as st


def check_review_password() -> bool:
    """Return True iff a valid review password is in session state.

    Renders the minimal centered password prompt as a side effect when
    not yet authenticated. Caller is expected to call ``st.stop()`` when
    this returns False so no review-only content renders.
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

    # ── Minimal centered gate UI ─────────────────────────────────────────────
    attempted = "review_password_correct" in st.session_state

    # Theme the password input to match the rest of the dark + gold app.
    st.markdown(
        """
        <style>
          [data-testid="stTextInput"] input {
            background: #0f1620 !important;
            border: 1px solid #2a3a52 !important;
            border-radius: 8px !important;
            color: #E6EDF3 !important;
            font-family: 'Inter', system-ui, sans-serif !important;
            font-size: 0.85rem !important;
            padding: 10px 14px !important;
            text-align: center !important;
            letter-spacing: 0.04em !important;
          }
          [data-testid="stTextInput"] input:focus {
            border-color: #D4A85A !important;
            box-shadow: 0 0 0 2px rgba(212,168,90,0.18) !important;
            outline: none !important;
          }
          [data-testid="stTextInput"] input::placeholder {
            color: #5a6a80 !important;
            text-align: center !important;
          }
          [data-testid="stAlert"] {
            border-radius: 8px !important;
            margin-top: 6px !important;
            font-size: 0.74rem !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Vertical spacer to push content into the optical center.
    st.markdown("<div style='height: 22vh;'></div>", unsafe_allow_html=True)

    # Narrow center column for the prompt.
    pad_l, center, pad_r = st.columns([1, 1.4, 1])

    with center:
        st.markdown(
            """
            <div style='text-align:center; margin-bottom:22px;'>
              <div style='font-size:1.5rem; color:#E6EDF3; font-weight:500;
                          letter-spacing:0.05em;'>
                Oriel CPI Demo
              </div>
              <div style='font-size:0.66rem; color:#8fa3b8;
                          letter-spacing:0.18em; margin-top:8px;
                          text-transform:uppercase;'>
                ForecastTrader Review
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.text_input(
            "Review password",
            type="password",
            on_change=_password_entered,
            key="review_password_input",
            label_visibility="collapsed",
            placeholder="Password",
        )

        if attempted:
            st.error("Incorrect password.")

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
