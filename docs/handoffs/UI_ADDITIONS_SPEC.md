# Exact UI additions — Oriel CPI Basis

## Card Row 1 — Reference Summary
| Card | Title | Subtitle | Footer |
|---|---|---|---|
| 1 | Official Print / Base Index | Published reference level | Snapshot UTC + age |
| 2 | 1M Implied | Near-term forward estimate | Confidence badge |
| 3 | 3M Implied | Primary commercialization underlier | Confidence badge + timestamp |
| 4 | 6M Implied | Longer tenor anchor | Confidence badge |
| 5 | Term Structure | `1M → 3M → 6M` slope summary | Regime tag |
| 6 | Publishability / Confidence | 0–100 score + status | Methodology version |

## Card Row 2 — Basis / Perpification
| Card | Title | Footer |
|---|---|---|
| 1 | Spot Index | "Observed blended reference" |
| 2 | Fair Value | "Model-derived underlier" |
| 3 | Simulated Perp | "Indicative perp anchor" |
| 4 | Basis | "Perp – FV or venue – blend basis" |
| 5 | Annualized Carry | "Indicative annualized carry" |

## Panel 3 — Source Blend / Governance
Left: score table  
Right: methodology text, weighting rule, eligibility rule, fallback rule, timestamp commentary

## Panel 4 — Distribution / Confidence
Left: line chart of 1M / 3M / 6M with optional 1σ band  
Right: probability table + blended std dev + constituent dispersion

## Panel 5 — Timestamp / Freshness Diagnostics
| Venue | Median Age | Max Age | Fresh % | Stale % | Snapshot Span | Cross-Venue Gap | Comment |
|---|---:|---:|---:|---:|---:|---:|---|