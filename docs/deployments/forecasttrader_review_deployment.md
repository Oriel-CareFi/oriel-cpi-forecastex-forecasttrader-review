# ForecastTrader Review Deployment Handoff

## Objective

Create a separate review-only Streamlit deployment for ForecastTrader using the same GitHub repository, but isolated on its own branch and Streamlit app instance.

This deployment should be suitable for external review and should not disrupt the existing production/demo Streamlit deployment.

---

## Target Configuration

| Item | Value |
|---|---|
| GitHub repo | Same repo as current CPI Streamlit app |
| Review branch | `forecasttrader-review` |
| Streamlit app URL | `https://oriel-cpi-forecasttrader.streamlit.app` |
| Access mode | Private |
| Viewers | Invited ForecastTrader / IBKR email addresses only |
| Purpose | External review build for ForecastTrader |
| Recommended app footer | `Oriel CPI Demo | Illustrative review build for ForecastTrader | Not production trading infrastructure` |

---

## High-Level Approach

Do **not** rename or overwrite the existing Streamlit app.

Instead:

1. Create a dedicated GitHub branch named `forecasttrader-review`.
2. Sanitize and stabilize the app on that branch for external review.
3. Deploy a **new Streamlit Community Cloud app** from that branch.
4. Assign the Streamlit subdomain: `oriel-cpi-forecasttrader`.
5. Set the app to **private**.
6. Invite ForecastTrader reviewers by email.

This creates a clean, review-only instance while preserving the existing deployment.

---

## Step 1 — Confirm the Correct Repository

The review deployment should be created from the same repository currently used for the CPI Streamlit demo.

Based on the current GitHub view, likely candidates are:

- `clangley-oriel/kalshi-inflation-index-demo-personal`
- `Collateral-Velocity/kalshi-inflation-index-demo`

Use the repo that is currently connected to the working Streamlit app unless instructed otherwise.

Before proceeding, confirm:

- the repo contains the current Streamlit app entrypoint;
- the existing deployment works;
- the app can run locally from the repo;
- the repository has no secrets committed in source files.

---

## Step 2 — Create the Review Branch

From the current working branch, create and push the review branch:

```bash
git checkout main
git pull origin main

git checkout -b forecasttrader-review
git push -u origin forecasttrader-review
```

If the current production branch is not `main`, replace `main` with the branch currently used by the working Streamlit app.

---

## Step 3 — Add a Repo-Level Handoff Folder

Create a repo folder for external deployment documentation:

```bash
mkdir -p docs/deployments
```

Save this handoff file inside the repo at:

```text
docs/deployments/forecasttrader_review_deployment.md
```

Commit it to the `forecasttrader-review` branch:

```bash
git add docs/deployments/forecasttrader_review_deployment.md
git commit -m "Add ForecastTrader review deployment handoff"
git push
```

---

## Step 4 — Create Review-Specific App Settings

Add a lightweight review configuration so the app can clearly identify itself as the ForecastTrader review build.

Recommended approach: create a file such as:

```text
config/review_build.py
```

Suggested contents:

```python
REVIEW_BUILD = True
REVIEW_AUDIENCE = "ForecastTrader"
REVIEW_APP_LABEL = "Oriel CPI Demo — ForecastTrader Review"
REVIEW_FOOTER = "Oriel CPI Demo | Illustrative review build for ForecastTrader | Not production trading infrastructure"
```

Then wire this into the Streamlit app footer/sidebar/header without changing core functionality.

If the app already has a config system, add the equivalent values there instead of creating a new pattern.

---

## Step 5 — Sanitize the Review Branch

Before deploying externally, ensure the `forecasttrader-review` branch is suitable for outside reviewers.

### Required

- Remove or hide internal-only notes, debug outputs, stack traces, and development banners.
- Ensure no API keys, tokens, private endpoints, or secrets are committed in the repo.
- Ensure any live API credentials are stored only in Streamlit Secrets.
- Use sample, public, or sanitized data unless explicit approval is given for live data.
- Add a visible disclaimer that this is an illustrative review build, not production trading infrastructure.
- Ensure app tabs appear in the intended meeting narrative order.
- Confirm that the app does not expose repo links, developer-only controls, admin paths, or raw logs.

### Recommended

- Keep the ForecastTrader review build focused on:
  - CPI as the bridge market;
  - prediction-market contract normalization;
  - conversion of discrete event prices into a continuous CPI curve;
  - institutional workflow/readiness;
  - extension path into healthcare inflation / medical CPI;
  - optional applicability to other macro categories such as weather.

---

## Step 6 — Confirm the Streamlit Entrypoint

Identify the app’s entry file, for example:

```text
streamlit_app.py
```

or:

```text
app.py
```

or another existing entrypoint.

This exact file path will be needed when creating the new Streamlit app.

Test locally from the review branch:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Replace `streamlit_app.py` with the actual entrypoint if different.

---

## Step 7 — Confirm Dependencies

Make sure the repo contains a working `requirements.txt`.

If the app relies on Python version constraints, add or confirm:

```text
runtime.txt
```

Example:

```text
python-3.11
```

Only add this if consistent with the current deployment.

---

## Step 8 — Configure Secrets for the New Streamlit App

Do not commit secrets into GitHub.

Any required environment variables or API credentials should be entered in the new Streamlit app’s Secrets panel.

In Streamlit Community Cloud:

1. Open the new app.
2. Go to **Settings**.
3. Open **Secrets**.
4. Add required values using TOML format.

Example only:

```toml
KALSHI_ENABLE_LIVE_CPI = "false"

[review]
audience = "ForecastTrader"
build = "external_review"
```

If the review app should use sample data only, explicitly disable live feeds where possible.

---

## Step 9 — Deploy a Separate Streamlit Instance

Go to:

```text
https://share.streamlit.io
```

Create a **new app**.

Use:

| Field | Value |
|---|---|
| Repository | Same repo as current CPI app |
| Branch | `forecasttrader-review` |
| Main file path | Existing Streamlit entrypoint, e.g. `streamlit_app.py` |
| App URL / subdomain | `oriel-cpi-forecasttrader` |

After deployment, the target URL should be:

```text
https://oriel-cpi-forecasttrader.streamlit.app
```

Important: this should be a new app instance, not a rename of the existing Streamlit deployment.

---

## Step 10 — Set the App to Private

In Streamlit Community Cloud:

1. Open the new app.
2. Go to **Share** or **Settings**.
3. Set access to **Private**.
4. Invite specific ForecastTrader / IBKR reviewers by email.
5. Confirm that invited users must authenticate using the same email address.

The app should not be public unless explicitly approved.

---

## Step 11 — Smoke Test Access

Before sending the link externally:

### Internal test

1. Open the app while logged into the Streamlit owner account.
2. Confirm the app loads.
3. Confirm all tabs render.
4. Confirm no secrets or internal paths are visible.
5. Confirm sample/live data behavior is correct.

### Private access test

1. Open an incognito/private browser window.
2. Visit:

```text
https://oriel-cpi-forecasttrader.streamlit.app
```

Expected result:

- If private access is correctly enabled, the browser should show a sign-in/access prompt.
- It should not open directly to the app unless the reviewer has been invited and authenticated.

### Invited-viewer test

Invite one internal test email first.

Confirm:

- the invitation arrives;
- the user can authenticate;
- the app loads successfully;
- the user does not receive repo access;
- the user only receives app-view access.

---

## Step 12 — Suggested External Review Note

Use or adapt the following when sending the link:

> Sharing the Oriel CPI demo link ahead of our conversation so your team can review the workflow in advance:
>
> https://oriel-cpi-forecasttrader.streamlit.app
>
> The app is an illustrative review build showing how Oriel can translate discrete inflation prediction-market signals into a continuous, institution-usable CPI curve and trading workflow. The near-term focus is CPI as the bridge; the broader opportunity is extending the same reference and execution layer into healthcare inflation and other macro contract categories.

---

## Step 13 — Optional Cleanup / Hardening Before External Review

Recommended before sending to ForecastTrader:

- Rename any visible references from “Kalshi Inflation Index Demo Personal” to “Oriel CPI Demo”.
- Avoid language that implies ForecastTrader data is being scraped or reverse-engineered.
- Use “ForecastTrader review build” rather than “ForecastTrader integration” unless an actual integration exists.
- Avoid “cross-venue diagnostics” in external-facing copy if that creates partner sensitivity.
- Use language such as:
  - “venue-normalized CPI signals”;
  - “event-contract signal translation”;
  - “institutional CPI curve workflow”;
  - “reference and execution layer for macro surfaces.”

---

## Step 14 — Rollback Plan

Because this is a separate branch and separate Streamlit instance, rollback is simple:

1. Disable or delete the `oriel-cpi-forecasttrader` Streamlit app.
2. Leave the existing app untouched.
3. Continue development on the original branch/app.

If a bad commit is pushed to the review branch:

```bash
git checkout forecasttrader-review
git log --oneline
git revert <bad_commit_hash>
git push
```

---

## Acceptance Criteria

The handoff is complete when:

- `forecasttrader-review` branch exists in GitHub.
- This handoff file is committed under `docs/deployments/`.
- A separate Streamlit app is deployed from the `forecasttrader-review` branch.
- The app URL is:

```text
https://oriel-cpi-forecasttrader.streamlit.app
```

- The app is private.
- ForecastTrader reviewers can be invited by email.
- Incognito access confirms the app is not publicly accessible.
- The existing Streamlit deployment remains unchanged.
