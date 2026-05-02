from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import math

from analytics.medical_basis_contract import (
    DEFAULT_THRESHOLDS_BPS,
    build_basis_curve,
    contract_spec_dataframe,
    expected_spread_bps,
    ladder_to_distribution,
    load_sample_medical_basis_contracts,
    repair_exceedance_ladder,
    settlement_example,
    settle_medical_basis_contract,
)


def test_sample_ladder_loads_with_expected_thresholds():
    df = load_sample_medical_basis_contracts()
    assert not df.empty
    assert {"maturity", "threshold_bps", "yes_price", "observation_window"}.issubset(df.columns)
    assert tuple(sorted(df["threshold_bps"].unique())) == DEFAULT_THRESHOLDS_BPS
    assert df["yes_price"].between(0, 1).all()


def test_ladder_to_distribution_sums_to_one():
    dist, repaired = ladder_to_distribution([0, 100, 200, 300, 400], [0.80, 0.60, 0.35, 0.20, 0.05])
    assert repaired is False
    assert len(dist) == 6
    assert math.isclose(float(dist["probability"].sum()), 1.0, rel_tol=1e-9)
    assert expected_spread_bps(dist) > 0


def test_monotonic_repair_prevents_negative_bucket_probabilities():
    repaired, changed = repair_exceedance_ladder([0.50, 0.70, 0.40])
    assert changed is True
    assert repaired == [0.50, 0.50, 0.40]

    dist, repaired_flag = ladder_to_distribution([0, 100, 200], [0.50, 0.70, 0.40])
    assert repaired_flag is True
    assert (dist["probability"] >= 0).all()
    assert math.isclose(float(dist["probability"].sum()), 1.0, rel_tol=1e-9)


def test_build_basis_curve_outputs_maturities_and_expected_spread():
    df = load_sample_medical_basis_contracts()
    curve = build_basis_curve(df)
    assert len(curve.points) == 4
    assert not curve.distribution.empty
    assert all(p.expected_spread_bps > 0 for p in curve.points)
    assert curve.points[0].probability_spread_gt_200 > 0


def test_settlement_example_matches_slide():
    result = settlement_example()
    assert result.cpi_yoy_pct == 3.1
    assert result.medical_cpi_yoy_pct == 5.6
    assert math.isclose(result.spread_bps, 250.0)
    assert result.threshold_bps == 200
    assert result.settles_yes is True
    assert result.payout == 1.0


def test_settlement_no_when_spread_does_not_exceed_threshold():
    result = settle_medical_basis_contract(cpi_yoy_pct=3.1, medical_cpi_yoy_pct=4.9, threshold_bps=200)
    assert math.isclose(result.spread_bps, 180.0)
    assert result.settles_yes is False
    assert result.payout == 0.0


def test_contract_spec_dataframe_has_reference_legs():
    df = contract_spec_dataframe()
    assert "Reference leg 1" in set(df["Field"])
    assert "Reference leg 2" in set(df["Field"])
    assert df.loc[df["Field"] == "Reference leg 1", "Value"].iloc[0] == "BLS CPI-U YoY"
    assert df.loc[df["Field"] == "Reference leg 2", "Value"].iloc[0] == "BLS Medical Care CPI YoY"
