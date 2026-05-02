# ForecastTrader Review Deployment — Public Streamlit App with Password Gate

## Objective

Create a separate ForecastTrader review deployment from the existing Oriel CPI Streamlit repo without disrupting the current private Streamlit app.

Because Streamlit Community Cloud allows only one private app per workspace, the recommended workaround is:

- deploy a separate **public** Streamlit app instance from the `forecasttrader-review` branch;
- use a simple **app-level password gate** inside Streamlit;
- store the password in **Streamlit Secrets**, not in GitHub;
- keep the existing private Streamlit app untouched.

---

## Target Configuration

| Item | Value |
|---|---|
| GitHub repository | `clangley-oriel/kalshi-inflation-index-demo-personal` |
| Branch | `forecasttrader-review` |
| Main file path | `app.py` |
| Streamlit URL | `https://oriel-cpi-forecasttrader.streamlit.app` |
| Streamlit visibility | Public |
| App-level access | Password-gated |
| Password storage | Streamlit Secrets |
| Existing app | Leave unchanged |

---

## Why This Approach

The original preferred setup was a separate Streamlit app with private invited-viewer access. However, Streamlit Community Cloud appears to limit the workspace to one private app. Since the existing app is already private, the clean workaround is to create a second public app URL and restrict access inside the app using a password gate.

This gives ForecastTrader a clean review URL while avoiding changes to the current deployment.

---

## Step 1 — Confirm You Are on the Review Branch

In GitHub, confirm the branch exists:

```text
forecasttrader-review
```

From local terminal:

```bash
git checkout forecasttrader-review
git pull origin forecasttrader-review
```

If the branch does not exist:

```bash
git checkout main
git pull origin main
git checkout -b forecasttrader-review
git push -u origin forecasttrader-review
```

If the production branch is not `main`, replace `main` with the branch currently used by the working app.

---

## Step 2 — Add a Password Gate to `app.py`

At the very top of `app.py`, before the app renders any tabs, data, charts, or page content, add:

```python
import hmac
import streamlit as st

def check_review_password() -> bool:
    """Simple password gate for external review builds.

    Password should be stored in Streamlit Secrets as:
        review_password = "your-password-here"

    Do not commit the password to GitHub.
    """

    def password_entered():
        entered_password = st.session_state.get("review_password_input", "")
        expected_password = st.secrets.get("review_password", "")

        if expected_password and hmac.compare_digest(entered_password, expected_password):
            st.session_state["review_password_correct"] = True
            del st.session_state["review_password_input"]
        else:
            st.session_state["review_password_correct"] = False

    if st.session_state.get("review_password_correct", False):
        return True

    st.title("Oriel CPI Demo")
    st.caption("ForecastTrader review build")

    st.text_input(
        "Review password",
        type="password",
        on_change=password_entered,
        key="review_password_input",
    )

    if "review_password_correct" in st.session_state:
        st.error("Password incorrect.")

    return False


if not check_review_password():
    st.stop()
```

### Important

This block must run before any sensitive or review-only content is rendered.

If `app.py` already imports `streamlit as st`, do not duplicate the import. Just keep one import at the top.

---

## Step 3 — Optional: Only Enable the Password Gate for Review Builds

If the same code may later be merged back into `main`, use a review flag so the password gate only applies to this deployment.

In Streamlit Secrets, set:

```toml
REVIEW_BUILD = "true"
review_password = "choose-a-strong-review-password"
```

Then wrap the password check like this:

```python
REVIEW_BUILD = str(st.secrets.get("REVIEW_BUILD", "false")).lower() == "true"

if REVIEW_BUILD and not check_review_password():
    st.stop()
```

For the `forecasttrader-review` branch, either approach is fine. The review-flag approach is safer if the branch may be merged later.

---

## Step 4 — Add Review Build Label / Footer

Add a visible label or footer somewhere in the app UI:

```python
st.caption(
    "Oriel CPI Demo | Illustrative review build for ForecastTrader | "
    "Not production trading infrastructure"
)
```

Recommended placement:

- near the top of the home / overview page;
- or in the sidebar;
- or at the bottom of the app.

This helps make clear that the app is a review build, not a production trading system.

---

## Step 5 — Sanitize the Review Branch

Before deploying externally, confirm the review branch is appropriate for ForecastTrader / IBKR review.

### Required

- No hardcoded API keys or tokens.
- No committed credentials.
- No internal-only notes or debug logs.
- No stack traces or developer panels exposed in the UI.
- No private partner data.
- No sensitive live endpoints unless intentionally enabled and protected.
- Any secrets must be stored only in Streamlit Secrets.
- App must be clear that it is illustrative and not production trading infrastructure.

### Recommended

For the review build, default to sanitized / sample data unless live data is approved.

If live data is used, ensure all credentials are configured via Streamlit Secrets and not visible in app output.

---

## Step 6 — Commit the Review Changes

```bash
git status
git add app.py
git commit -m "Add password gate for ForecastTrader review deployment"
git push origin forecasttrader-review
```

If you also add a docs file inside the repo, use:

```bash
mkdir -p docs/deployments
```

Save this handoff as:

```text
docs/deployments/forecasttrader_password_gated_review_deployment.md
```

Then commit:

```bash
git add docs/deployments/forecasttrader_password_gated_review_deployment.md
git commit -m "Add ForecastTrader password-gated deployment handoff"
git push origin forecasttrader-review
```

---

## Step 7 — Create the New Streamlit App

Go to Streamlit Community Cloud:

```text
https://share.streamlit.io
```

Click:

```text
Create app
```

Fill in the deployment form as follows:

```text
Repository:
clangley-oriel/kalshi-inflation-index-demo-personal
```

```text
Branch:
forecasttrader-review
```

```text
Main file path:
app.py
```

```text
App URL:
oriel-cpi-forecasttrader
```

Click:

```text
Deploy
```

The resulting URL should be:

```text
https://oriel-cpi-forecasttrader.streamlit.app
```

Because of the Streamlit Community Cloud private-app limit, deploy this as a public app. The in-app password gate will restrict access to the app content.

---

## Step 8 — Add the Password in Streamlit Secrets

After the app is created:

1. Open the new app in Streamlit Cloud.
2. Click the three-dot menu.
3. Open **Settings**.
4. Go to **Secrets**.
5. Add:

```toml
review_password = "choose-a-strong-review-password"
REVIEW_BUILD = "true"
```

Use a real strong password and share it only with intended reviewers.

Do **not** commit this password to GitHub.

Save the secrets and reboot the app if Streamlit does not restart automatically.

---

## Step 9 — Smoke Test the Deployment

### Owner test

Open:

```text
https://oriel-cpi-forecasttrader.streamlit.app
```

Confirm:

- the app loads;
- the password prompt appears first;
- the correct password unlocks the app;
- the wrong password is rejected;
- no app content appears before password entry.

### Incognito test

Open an incognito / private browser window and visit:

```text
https://oriel-cpi-forecasttrader.streamlit.app
```

Expected behavior:

- the page should load publicly;
- the app content should not be visible;
- only the password gate should appear;
- entering the password should unlock the app.

### Content test

After unlocking, confirm:

- tabs load correctly;
- no secrets or internal paths are visible;
- the app uses the correct ForecastTrader review branch;
- review footer / disclaimer appears;
- app language is external-review appropriate.

---

## Step 10 — Suggested External Note

Use this language when sending the link:

```text
Sharing the Oriel CPI review build ahead of our conversation:

https://oriel-cpi-forecasttrader.streamlit.app

The app is password-protected for external review.

Password: [insert password]

This is an illustrative review build showing how Oriel can translate discrete inflation prediction-market signals into a continuous, institution-usable CPI curve and trading workflow. CPI is the practical on-ramp; the broader opportunity is extending the same reference and execution layer into healthcare inflation and other macro contract categories.
```

---

## Step 11 — Recommended App Positioning

Avoid describing this as a ForecastTrader integration unless there is an actual integration.

Use language such as:

- ForecastTrader review build
- Oriel CPI demo
- CPI event-contract workflow
- venue-normalized CPI signals
- institution-grade CPI curve workflow
- reference and execution-intelligence layer for macro surfaces

Avoid sensitive phrasing such as:

- scraping ForecastTrader
- reverse-engineering
- exploiting ForecastTrader
- cross-venue surveillance

---

## Step 12 — Rollback Plan

If anything breaks:

1. Delete or pause the new Streamlit app instance.
2. Leave the existing private app untouched.
3. Revert the latest review-branch commit:

```bash
git checkout forecasttrader-review
git log --oneline
git revert <bad_commit_hash>
git push origin forecasttrader-review
```

Because this deployment uses a separate branch and separate app URL, rollback should not affect the existing main app.

---

## Acceptance Criteria

The deployment is complete when:

- `forecasttrader-review` branch exists.
- Password gate is present at the top of `app.py`.
- Password is stored in Streamlit Secrets, not GitHub.
- New Streamlit app is deployed at:

```text
https://oriel-cpi-forecasttrader.streamlit.app
```

- App content is inaccessible without the review password.
- Existing private app remains unchanged.
- ForecastTrader can access the app using the URL and password.
