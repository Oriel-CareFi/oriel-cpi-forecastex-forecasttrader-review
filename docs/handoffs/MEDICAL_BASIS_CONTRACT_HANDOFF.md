# ForecastEx Medical Inflation Basis Contract — Developer Handoff

## What this patch adds

This drop-in patch adds an illustrative ForecastEx-style medical inflation basis contract layer to the Oriel app.

It implements the eight requested items:

1. **CPI-U and Medical CPI YoY reference legs** via `MedicalBasisContractSpec` and `ReferenceLeg`.
2. **Spread threshold ladder** using thresholds `0, 100, 200, 300, 400 bps`.
3. **Sample YES prices** in `data/medical_basis_sample_contracts.csv`.
4. **Implied spread distribution** via `ladder_to_distribution()`.
5. **Expected medical-vs-CPI basis** via `expected_spread_bps()` and `build_basis_curve()`.
6. **Basis curve rendering support** in `tabs/medical_basis_tab.py`.
7. **Settlement example**: Medical CPI `5.6%` vs CPI `3.1%`, spread `250 bps`, threshold `200 bps`, settles YES / `$1.00`.
8. **Associated UI elements** through a new Streamlit tab: `ForecastEx Medical Basis`.

## Files added

```text
analytics/medical_basis_contract.py
data/medical_basis_sample_contracts.csv
tabs/medical_basis_tab.py
tests/test_medical_basis_contract.py
MEDICAL_BASIS_CONTRACT_HANDOFF.md
```

## Files modified

```text
app.py
tabs/__init__.py
```

## UI placement

The patch adds a new top-level tab immediately after `Oriel Healthcare Reference`:

```text
ForecastEx Medical Basis
```

The tab includes:

- ForecastEx-style header and valuation date
- reference-leg cards for CPI-U and Medical Care CPI
- KPI cards for expected basis, P(spread > 200 bps), settlement example, and thresholds
- contract-spec table
- objective settlement calculator
- threshold-ladder chart
- implied distribution chart
- market-implied basis curve
- data expander with the sample ladder

## Economic interpretation

The sample ladder represents YES prices for binary contracts of the form:

```text
Medical CPI YoY - CPI-U YoY > threshold_bps
```

For example:

```text
Question: Will U.S. medical inflation exceed U.S. headline CPI inflation by more than 200 bps?
Settlement: $1.00 if Medical CPI YoY - CPI-U YoY > 2.00%; otherwise $0.00
```

## Why monotonic repair is included

Threshold ladders must be monotonic:

```text
P(spread > 400 bps) <= P(spread > 300 bps) <= P(spread > 200 bps) <= ...
```

The module includes deterministic monotonic repair so invalid sample/live ladders do not produce negative bucket probabilities.

## Test command

```bash
python -m pytest tests/test_medical_basis_contract.py -q
```

Expected result:

```text
7 passed
```

## Future live integration points

When ForecastEx or another venue lists a medical-vs-CPI contract family, replace the sample CSV load in `tabs/medical_basis_tab.py` with a venue adapter that returns the same normalized fields:

```text
maturity
observation_window
threshold_bps
yes_price
bid
ask
volume
open_interest
source
source_status
contract_label
```

No UI changes should be required if the adapter preserves this schema.

## Phase II extension

The initial reference leg uses BLS Medical Care CPI because it is public and objective. The same module can support a later Oriel/CareFi claims-based medical trend index by changing `reference_leg_2` and feeding the resulting curve into the same threshold-ladder and settlement framework.
