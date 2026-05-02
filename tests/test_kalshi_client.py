"""
tests/test_kalshi_client.py — Unit tests for KalshiPublicClient.

Tests transport, retry logic, fallback host, and error normalization.
No real network calls — all mocked.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch, call
from requests.exceptions import ConnectionError as ReqConnectionError, Timeout as ReqTimeout

from venues.kalshi.client import (
    KalshiAPIError,
    KalshiClientConfig,
    KalshiPublicClient,
    _build_session,
)


def _mock_response(status_code: int = 200, json_data: dict = None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


# ── Config ────────────────────────────────────────────────────────────────────

def test_config_defaults():
    cfg = KalshiClientConfig()
    assert "kalshi" in cfg.base_url.lower()
    assert cfg.timeout_seconds > 0
    assert cfg.max_retries > 0
    assert cfg.backoff_seconds >= 0


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("KALSHI_TIMEOUT_SECONDS", "42")
    monkeypatch.setenv("KALSHI_MAX_RETRIES", "3")
    cfg = KalshiClientConfig()
    assert cfg.timeout_seconds == 42.0
    assert cfg.max_retries == 3


# ── Successful request ────────────────────────────────────────────────────────

def test_request_success():
    client = KalshiPublicClient()
    mock_resp = _mock_response(200, {"markets": [{"ticker": "KXCPI-TEST"}], "cursor": None})
    client.session.get = MagicMock(return_value=mock_resp)
    result = client._request("markets", {"series_ticker": "KXCPI"})
    assert result["markets"][0]["ticker"] == "KXCPI-TEST"


# ── Error normalization ───────────────────────────────────────────────────────

def test_rate_limit_raises_kalshi_error():
    client = KalshiPublicClient()
    client.session.get = MagicMock(return_value=_mock_response(429))
    with pytest.raises(KalshiAPIError) as exc_info:
        client._request("markets")
    assert exc_info.value.status_code == 429
    assert "rate limit" in str(exc_info.value).lower()


def test_server_error_raises_kalshi_error():
    client = KalshiPublicClient()
    client.session.get = MagicMock(return_value=_mock_response(503))
    with pytest.raises(KalshiAPIError) as exc_info:
        client._request("markets")
    assert exc_info.value.status_code == 503


def test_client_error_raises_kalshi_error():
    client = KalshiPublicClient()
    client.session.get = MagicMock(return_value=_mock_response(404, text="Not found"))
    with pytest.raises(KalshiAPIError) as exc_info:
        client._request("markets/NONEXISTENT")
    assert exc_info.value.status_code == 404


def test_timeout_raises_kalshi_error():
    client = KalshiPublicClient()
    client.session.get = MagicMock(side_effect=ReqTimeout("timed out"))
    with pytest.raises(KalshiAPIError):
        client._request("markets")


def test_connection_error_raises_kalshi_error():
    client = KalshiPublicClient()
    client.session.get = MagicMock(side_effect=ReqConnectionError("connection refused"))
    with pytest.raises(KalshiAPIError):
        client._request("markets")


def test_bad_json_raises_kalshi_error():
    client = KalshiPublicClient()
    mock_resp = _mock_response(200)
    mock_resp.json.side_effect = ValueError("no JSON")
    client.session.get = MagicMock(return_value=mock_resp)
    with pytest.raises(KalshiAPIError) as exc_info:
        client._request("markets")
    assert "non-json" in str(exc_info.value).lower()


# ── Fallback host ─────────────────────────────────────────────────────────────

def test_fallback_host_used_on_primary_failure():
    cfg = KalshiClientConfig()
    client = KalshiPublicClient(config=cfg)

    success_resp = _mock_response(200, {"markets": [], "cursor": None})
    # First call (primary) raises connection error, second (fallback) succeeds
    client.session.get = MagicMock(side_effect=[
        ReqConnectionError("primary down"),
        success_resp,
    ])
    with patch("time.sleep"):
        result = client._request("markets")
    assert result == {"markets": [], "cursor": None}
    assert client.session.get.call_count == 2


def test_fallback_disabled():
    cfg = KalshiClientConfig()
    object.__setattr__(cfg, "try_fallback_host", False)
    client = KalshiPublicClient(config=cfg)
    client.session.get = MagicMock(side_effect=ReqConnectionError("primary down"))
    with pytest.raises(KalshiAPIError):
        client._request("markets")
    assert client.session.get.call_count == 1


def test_all_hosts_fail_raises_kalshi_error():
    client = KalshiPublicClient()
    client.session.get = MagicMock(side_effect=ReqConnectionError("all down"))
    with patch("time.sleep"):
        with pytest.raises(KalshiAPIError) as exc_info:
            client._request("markets")
    assert "all hosts" in str(exc_info.value).lower()


# ── Pagination ────────────────────────────────────────────────────────────────

def test_iter_markets_paginates():
    client = KalshiPublicClient()
    page1 = _mock_response(200, {"markets": [{"ticker": "A"}], "cursor": "next"})
    page2 = _mock_response(200, {"markets": [{"ticker": "B"}], "cursor": None})
    client.session.get = MagicMock(side_effect=[page1, page2])
    markets = list(client.iter_markets(series_ticker="KXCPI"))
    assert [m["ticker"] for m in markets] == ["A", "B"]
    assert client.session.get.call_count == 2


def test_iter_markets_empty():
    client = KalshiPublicClient()
    client.session.get = MagicMock(return_value=_mock_response(200, {"markets": [], "cursor": None}))
    markets = list(client.iter_markets(series_ticker="KXCPI"))
    assert markets == []


def test_get_market_success():
    client = KalshiPublicClient()
    client.session.get = MagicMock(return_value=_mock_response(200, {"market": {"ticker": "KXCPI-26MAR"}}))
    result = client.get_market("KXCPI-26MAR")
    assert result["ticker"] == "KXCPI-26MAR"


def test_get_market_missing_key():
    client = KalshiPublicClient()
    client.session.get = MagicMock(return_value=_mock_response(200, {}))
    result = client.get_market("KXCPI-UNKNOWN")
    assert result == {}
