"""
tests/test_phase2_live_data.py — Unit tests for phase2_live_data transformation layer.

Tests reference-month parsing, quote selection, liquidity filtering,
contract classification, maturity grouping, and edge cases.
No real network calls.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
from unittest.mock import MagicMock, patch

from venues.kalshi.live_data import (
    LiveFeedConfig,
    _extract_reference_cpi_month,
    _extract_strike_value,
    _choose_probability,
    _contract_type,
    _threshold_direction,
    _liquidity_metrics,
    build_live_cpi_feed,
)
from venues.kalshi.client import KalshiAPIError


# ── Reference month parsing ───────────────────────────────────────────────────

@pytest.mark.parametrize("ticker,expected", [
    ("KXCPI-26MAR",          date(2026, 3, 1)),
    ("KXCPI-26APR",          date(2026, 4, 1)),
    ("KXCPI-2026APR",        date(2026, 4, 1)),
    ("KXCPI-APR26",          date(2026, 4, 1)),
    ("KXCPI-2026-04",        date(2026, 4, 1)),
    ("CPI April 2026",       date(2026, 4, 1)),
    ("CPI 2026 April",       date(2026, 4, 1)),
])
def test_reference_month_from_ticker(ticker, expected):
    market = {"ticker": ticker}
    result = _extract_reference_cpi_month(market)
    assert result == expected, f"ticker={ticker!r}: got {result}, expected {expected}"


def test_reference_month_from_expiry_fallback():
    """If no month in ticker, use expiry - 1 month."""
    market = {
        "ticker": "KXCPI-UNKNOWN",
        "expiration_time": "2026-05-15T00:00:00Z",  # May expiry → April reference
    }
    result = _extract_reference_cpi_month(market)
    assert result == date(2026, 4, 1)


def test_reference_month_none_on_unparseable():
    market = {"ticker": "NOMATCH", "title": "something unrelated"}
    result = _extract_reference_cpi_month(market)
    assert result is None


def test_reference_month_from_event_metadata():
    market = {
        "ticker": "KXCPI-ABC",
        "event": {"title": "CPI March 2026 Report"},
    }
    result = _extract_reference_cpi_month(market)
    assert result == date(2026, 3, 1)


# ── Strike value extraction ───────────────────────────────────────────────────

def test_strike_from_strike_dict():
    market = {"strike": {"value": 3.2}}
    assert _extract_strike_value(market) == 3.2


def test_strike_from_subtitle():
    market = {"subtitle": "CPI above 3.5%"}
    assert _extract_strike_value(market) == 3.5


def test_strike_from_title_no_percent():
    market = {"title": "Will CPI be 3.3"}
    assert _extract_strike_value(market) == 3.3


def test_strike_none_when_missing():
    market = {"title": "no numbers here at all"}
    assert _extract_strike_value(market) is None


# ── Quote selection ───────────────────────────────────────────────────────────

def test_yes_mid_preferred():
    market = {"yes_bid": 0.40, "yes_ask": 0.60}
    prob, sel = _choose_probability(market, price_mode="mid")
    assert prob == pytest.approx(0.50)
    assert "mid" in sel.chosen_price_reason


def test_yes_bid_mode():
    market = {"yes_bid": 0.40, "yes_ask": 0.60}
    prob, sel = _choose_probability(market, price_mode="bid")
    assert prob == pytest.approx(0.40)


def test_synthetic_mid_fallback():
    market = {"yes_bid": 0.45, "no_bid": 0.50}  # no ask
    prob, sel = _choose_probability(market, price_mode="mid")
    assert prob is not None
    assert "synthetic" in sel.chosen_price_reason


def test_last_trade_fallback():
    market = {"last_price": 0.55}
    prob, sel = _choose_probability(market, price_mode="mid")
    assert prob == pytest.approx(0.55)
    assert "last" in sel.chosen_price_reason


def test_no_price_returns_none():
    market = {}
    prob, sel = _choose_probability(market, price_mode="mid")
    assert prob is None
    assert "no_usable" in sel.chosen_price_reason


def test_probability_clamped_to_unit_interval():
    market = {"yes_bid": -0.1, "yes_ask": 1.5}
    prob, _ = _choose_probability(market, price_mode="mid")
    # mid = (-0.1 + 1.5) / 2 = 0.7, then clamped
    assert 0.0 <= prob <= 1.0


# ── Contract classification ───────────────────────────────────────────────────

def test_binary_threshold_from_strike_type():
    market = {"strike_type": "greater_than", "title": "CPI", "subtitle": "", "ticker": "X"}
    assert _contract_type(market) == "binary_threshold"


def test_binary_threshold_from_title():
    market = {"strike_type": "", "title": "CPI above 3%", "subtitle": "", "ticker": "X"}
    assert _contract_type(market) == "binary_threshold"


def test_exact_outcome_default():
    market = {"strike_type": "", "title": "CPI equals 3.2%", "subtitle": "", "ticker": "X"}
    assert _contract_type(market) == "exact_outcome"


def test_threshold_direction_above():
    market = {"strike_type": "greater_than", "title": "", "subtitle": "", "ticker": ""}
    assert _threshold_direction(market) == "above"


def test_threshold_direction_below():
    market = {"strike_type": "less_than", "title": "", "subtitle": "", "ticker": ""}
    assert _threshold_direction(market) == "below"


# ── Liquidity filter ──────────────────────────────────────────────────────────

def test_liquidity_spread_computed():
    market = {"yes_bid": 0.40, "yes_ask": 0.50}
    oi, vol, spread = _liquidity_metrics(market)
    assert spread == pytest.approx(0.10)


def test_liquidity_spread_none_when_missing():
    market = {}
    oi, vol, spread = _liquidity_metrics(market)
    assert spread is None


# ── build_live_cpi_feed integration ──────────────────────────────────────────

def _make_market(ticker, month_str, strike, yes_bid, yes_ask, oi=50, vol=30,
                 strike_type="greater_than"):
    return {
        "ticker": ticker,
        "title": f"CPI {month_str}",
        "subtitle": f"above {strike}%",
        "event_ticker": f"KXCPI-{month_str.upper().replace(' ', '')}",
        "strike_type": strike_type,
        "strike": {"value": strike},
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "open_interest_fp": oi,
        "volume_fp": vol,
    }


def test_build_live_feed_success():
    markets = [
        _make_market("KXCPI-26MAR-ABOVE2.5", "26MAR", 2.5, 0.90, 0.95, oi=100, vol=50),
        _make_market("KXCPI-26MAR-ABOVE3.0", "26MAR", 3.0, 0.70, 0.75, oi=80,  vol=40),
        _make_market("KXCPI-26MAR-ABOVE3.5", "26MAR", 3.5, 0.20, 0.25, oi=60,  vol=30),
    ]
    mock_client = MagicMock()
    mock_client.iter_markets.return_value = iter(markets)

    methodology, snapshots, contracts_table, stats = build_live_cpi_feed(client=mock_client)

    assert len(snapshots) == 1
    assert snapshots[0].maturity == date(2026, 3, 1)
    assert len(snapshots[0].binary_thresholds) == 3
    assert stats["markets_included"] == 3
    assert stats["maturities_built"] == 1


def test_build_live_feed_filters_low_liquidity():
    markets = [
        _make_market("KXCPI-26MAR-ABOVE3.0", "26MAR", 3.0, 0.70, 0.75, oi=0, vol=0),
        _make_market("KXCPI-26MAR-ABOVE3.5", "26MAR", 3.5, 0.20, 0.25, oi=0, vol=0),
    ]
    mock_client = MagicMock()
    mock_client.iter_markets.return_value = iter(markets)

    cfg = LiveFeedConfig()
    with pytest.raises(ValueError, match="No valid CPI maturities"):
        build_live_cpi_feed(config=cfg, client=mock_client)


def test_build_live_feed_filters_wide_spread():
    # Spread = 0.90 - 0.10 = 0.80, exceeds default max of 0.20
    markets = [
        _make_market("KXCPI-26APR-ABOVE3.0", "26APR", 3.0, 0.10, 0.90, oi=100, vol=50),
        _make_market("KXCPI-26APR-ABOVE3.5", "26APR", 3.5, 0.10, 0.90, oi=100, vol=50),
    ]
    mock_client = MagicMock()
    mock_client.iter_markets.return_value = iter(markets)

    with pytest.raises(ValueError):
        build_live_cpi_feed(client=mock_client)


def test_build_live_feed_raises_on_empty():
    mock_client = MagicMock()
    mock_client.iter_markets.return_value = iter([])
    with pytest.raises(ValueError, match="No valid CPI maturities"):
        build_live_cpi_feed(client=mock_client)


def test_build_live_feed_skips_missing_maturity():
    markets = [
        {"ticker": "KXCPI-NOMATCH", "title": "something", "subtitle": "",
         "strike_type": "greater_than", "strike": {"value": 3.0},
         "yes_bid": 0.5, "yes_ask": 0.6, "open_interest_fp": 100, "volume_fp": 50},
    ]
    mock_client = MagicMock()
    mock_client.iter_markets.return_value = iter(markets)
    with pytest.raises(ValueError):
        build_live_cpi_feed(client=mock_client)


def test_build_live_feed_max_maturities_respected():
    # 4 maturities, max=2
    markets = []
    for month, mo in [("26MAR", 3), ("26APR", 4), ("26MAY", 5), ("26JUN", 6)]:
        for strike in [3.0, 3.5, 4.0]:
            markets.append(_make_market(
                f"KXCPI-{month}-ABOVE{strike}", month, strike,
                0.5, 0.6, oi=100, vol=50
            ))

    mock_client = MagicMock()
    mock_client.iter_markets.return_value = iter(markets)

    cfg = LiveFeedConfig()
    object.__setattr__(cfg, "max_maturities", 2)
    _, snapshots, _, stats = build_live_cpi_feed(config=cfg, client=mock_client)
    assert len(snapshots) <= 2
