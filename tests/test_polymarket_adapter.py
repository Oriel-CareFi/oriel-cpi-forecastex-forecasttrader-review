from datetime import datetime, timedelta, timezone

from venues.polymarket.client import PolymarketClient
from venues.polymarket.config import DEFAULT_CONFIG
from venues.polymarket.models import PolymarketContract
from venues.polymarket.transform import normalize_expected_value, publishability_reason, summarize_venue_eligibility

UTC = timezone.utc


def _contract(release_month="Mar 2026", spread=0.02, last_updated=None):
    return PolymarketContract(
        venue='Polymarket',
        market_id=f'{release_month}-id',
        slug='march-2026-cpi-above-2-8',
        question=f'Will {release_month} inflation be above 2.8%?',
        release_month=release_month,
        resolution_time=None,
        threshold=2.8,
        outcome='YES',
        outcome_price=0.52,
        bid=0.52 - spread / 2,
        ask=0.52 + spread / 2,
        last=0.52,
        mid=0.52,
        spread=spread,
        volume=500,
        open_interest=1000,
        liquidity_score=0.5,
        confidence_score=75.0,
        settlement_source='BLS CPI release',
        valuation_timestamp=datetime.now(UTC),
        expected_value=2.81,
        last_updated=last_updated or datetime.now(UTC),
        has_valid_quote=True,
        has_depth=True,
        depth_usd=1000,
        quote_age_seconds=30,
        is_stale=False,
    )


def test_extract_release_month_and_direction():
    assert PolymarketClient._extract_release_month('Will March 2026 inflation be above 2.8%?') == 'Mar 2026'
    fallback = datetime(2026, 4, 15, tzinfo=UTC)
    assert PolymarketClient._extract_release_month('Will inflation in April?', fallback_dt=fallback) == 'Apr 2026'
    assert PolymarketClient.extract_threshold_direction('Will March 2026 inflation be below 2.8%?') == 'below'
    assert PolymarketClient.extract_threshold_direction('Will March 2026 inflation be above 2.8%?') == 'above'


def test_normalize_expected_value_handles_below_markets():
    contract = _contract()
    contract.question = 'Will March 2026 inflation be below 2.8%?'
    contract.outcome_price = 0.70
    contract.bid = 0.69
    contract.ask = 0.71
    contract.mid = 0.70
    assert normalize_expected_value(contract) == 2.7


def test_publishability_reason_flags_diagnostic_only_for_wide_but_renderable_spread():
    contract = _contract(spread=0.02)
    assert publishability_reason(contract, DEFAULT_CONFIG) == 'diagnostic only'


def test_publishability_reason_catches_extreme_spread():
    contract = _contract(spread=0.60)
    assert publishability_reason(contract, DEFAULT_CONFIG) == 'wide spread'


def test_summarize_venue_eligibility_partial_when_renderable_but_not_publishable():
    contracts = [_contract('Apr 2026', spread=0.02), _contract('Dec 2026', spread=0.02)]
    summary = summarize_venue_eligibility(contracts, DEFAULT_CONFIG)
    assert summary.venue_status == 'partial'
    assert summary.reference_status == 'not_eligible'
    assert summary.publishable is False


def test_summarize_venue_eligibility_insufficient_when_only_one_maturity():
    summary = summarize_venue_eligibility([_contract('Apr 2026', spread=0.02)], DEFAULT_CONFIG)
    assert summary.venue_status == 'insufficient'
    assert summary.publishable is False


def test_stale_quote_fails_render_and_publish():
    contract = _contract(last_updated=datetime.now(UTC) - timedelta(hours=40))
    contract.quote_age_seconds = 2000
    contract.is_stale = True
    assert publishability_reason(contract, DEFAULT_CONFIG) == 'stale quote'
