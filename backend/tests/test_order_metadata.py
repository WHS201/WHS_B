"""Orders validate provider metadata; no live market/network requests."""
from decimal import Decimal

import pytest

from app.constants import Market, MarketSession
from app.extensions import db
from app.models.account import Account
from app.models.deposits_savings import LedgerTransaction
from app.models.market import MarketAsset, MarketHolding, MarketTransaction
from app.services import investment_service, market_data_service


@pytest.fixture
def listing(app, monkeypatch):
    fixtures = {}
    calls = {"ticker": [], "session": [], "fx": []}

    class Ticker:
        def __init__(self, symbol):
            calls["ticker"].append(symbol)
            self.info, self.fast_info = fixtures.get(symbol, ({}, {}))

        def get_info(self):
            return self.info

    monkeypatch.setattr(market_data_service.yf, "Ticker", Ticker)
    monkeypatch.setattr(market_data_service, "get_market_session",
                        lambda market: calls["session"].append(market) or MarketSession.REGULAR)
    monkeypatch.setattr(market_data_service, "fetch_exchange_rate",
                        lambda: calls["fx"].append(True) or Decimal("1300"))

    def add(symbol="AAPL", exchange="NMS", currency="USD", quote_type="EQUITY", **changes):
        info = {"symbol": symbol, "exchange": exchange, "currency": currency,
                "quoteType": quote_type, "shortName": "Test listing", **changes}
        fast = {"last_price": 100, "currency": currency}
        fixtures[symbol] = info, fast
        return info, fast

    Account.query.filter_by(user_id=1).one().balance = 1000000
    db.session.commit()
    return add, calls


def order(client, auth, symbol="AAPL", market="US", side="BUY"):
    return client.post("/api/investments/orders", headers=auth(), json={
        "symbol": symbol, "market": market, "side": side, "quantity": 1,
    })


def unchanged():
    assert Account.query.filter_by(user_id=1).one().balance == 1000000
    assert MarketTransaction.query.count() == 0
    assert MarketHolding.query.count() == 0
    assert LedgerTransaction.query.count() == 0


@pytest.mark.parametrize("symbol,exchange,currency,market", [
    ("AAPL", "NMS", "USD", "KR"), ("005930", "KSC", "KRW", "US"),
])
@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_request_market_mismatch_rejected_before_session_or_fx(client, auth, listing, symbol, exchange, currency, market, side):
    add, calls = listing
    add(symbol + ".KS" if currency == "KRW" else symbol, exchange, currency)
    response = order(client, auth, symbol, market, side)
    assert response.status_code == 422, response.json
    assert response.json["error"]["code"] == "ASSET_METADATA_MISMATCH"
    assert calls["session"] == calls["fx"] == []
    unchanged()


@pytest.mark.parametrize("changes", [
    {"currency": "KRW"}, {"exchange": "LSE"}, {"quote_type": "MUTUALFUND"},
    {"quote_type": "CRYPTOCURRENCY"}, {"quote_type": "FUTURE"},
])
def test_unsupported_metadata_rejected(client, auth, listing, changes):
    listing[0](**changes)
    assert order(client, auth).status_code == 422
    unchanged()


@pytest.mark.parametrize("field", ["symbol", "exchange", "currency", "quoteType"])
@pytest.mark.parametrize("value", [None, ""])
def test_incomplete_metadata_never_uses_guessed_defaults(client, auth, listing, field, value):
    info, _ = listing[0]()
    info[field] = value
    response = order(client, auth)
    assert response.status_code == 503
    assert response.json["error"]["code"] == "ASSET_METADATA_UNAVAILABLE"
    unchanged()


@pytest.mark.parametrize("field,value,code", [
    ("currency", "KRW", "ASSET_METADATA_MISMATCH"),
    ("currency", None, "ASSET_METADATA_MISMATCH"),
    ("last_price", None, "PRICE_UNAVAILABLE"),
    ("last_price", "NaN", "PRICE_UNAVAILABLE"),
    ("last_price", "Infinity", "PRICE_UNAVAILABLE"),
    ("last_price", 0, "PRICE_UNAVAILABLE"),
])
def test_price_must_be_finite_and_same_currency(client, auth, listing, field, value, code):
    _, fast = listing[0]()
    fast[field] = value
    response = order(client, auth)
    assert response.status_code in (422, 503)
    assert response.json["error"]["code"] == code
    unchanged()


def test_different_provider_symbol_is_rejected(client, auth, listing):
    info, _ = listing[0]()
    info["symbol"] = "MSFT"
    assert order(client, auth).status_code == 422
    unchanged()


def test_korean_suffix_must_match_the_reported_exchange(client, auth, listing):
    listing[0]("005930.KS", "KOE", "KRW")
    assert order(client, auth, "005930", "KR").status_code == 422
    unchanged()


def test_korean_suffix_uses_existing_active_state(client, auth, listing):
    listing[0]("005930.KS", "KSC", "KRW")
    db.session.add(MarketAsset(symbol="005930", name="Test", market="KR",
                               asset_type="STOCK", is_active=False))
    db.session.commit()
    response = order(client, auth, "005930.KS", "KR")
    assert response.status_code == 422
    assert response.json["error"]["code"] == "ASSET_INACTIVE"
    unchanged()


def test_korean_suffix_and_bare_code_share_one_holding(client, auth, listing):
    listing[0]("005930.KS", "KSC", "KRW")
    assert order(client, auth, "005930.KS", "KR").status_code == 201
    assert order(client, auth, "005930", "KR", "SELL").status_code == 201
    assert MarketAsset.query.one().symbol == "005930"
    assert MarketHolding.query.one().quantity == 0


def test_provider_outage_never_reuses_guessed_quote(client, auth, listing, monkeypatch):
    def unavailable(symbol):
        raise RuntimeError("synthetic provider outage")
    monkeypatch.setattr(market_data_service.yf, "Ticker", unavailable)
    response = order(client, auth)
    assert response.status_code == 503
    assert response.json["error"]["code"] == "ASSET_METADATA_UNAVAILABLE"
    unchanged()


@pytest.mark.parametrize("market,asset_type,active,code", [
    ("US", "STOCK", False, "ASSET_INACTIVE"),
    ("KR", "STOCK", True, "ASSET_METADATA_MISMATCH"),
    ("US", "ETF", True, "ASSET_METADATA_MISMATCH"),
])
@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_registered_metadata_and_active_state_enforced(client, auth, listing, market, asset_type, active, code, side):
    listing[0]()
    db.session.add(MarketAsset(symbol="AAPL", name="Test", market=market,
                               asset_type=asset_type, is_active=active))
    db.session.commit()
    response = order(client, auth, side=side)
    assert response.status_code == 422
    assert response.json["error"]["code"] == code
    unchanged()


@pytest.mark.parametrize("symbol,ticker,exchange,currency,market,kind", [
    ("005930", "005930.KS", "KSC", "KRW", "KR", "EQUITY"),
    ("035900", "035900.KQ", "KOE", "KRW", "KR", "EQUITY"),
    ("AAPL", "AAPL", "NMS", "USD", "US", "EQUITY"),
    ("069500", "069500.KS", "KSC", "KRW", "KR", "ETF"),
    ("SPY", "SPY", "PCX", "USD", "US", "ETF"),
])
def test_supported_stock_and_etf_buy_sell_keep_settlement(client, auth, listing, symbol, ticker, exchange, currency, market, kind):
    add, calls = listing
    add(ticker, exchange, currency, kind)
    for side in ("BUY", "SELL"):
        response = order(client, auth, symbol, market, side)
        assert response.status_code == 201, response.json
    asset = MarketAsset.query.filter_by(symbol=symbol).one()
    assert asset.market == market
    assert asset.asset_type == ("ETF" if kind == "ETF" else "STOCK")
    assert asset.is_active
    rows = MarketTransaction.query.order_by(MarketTransaction.market_transaction_id).all()
    assert [row.side for row in rows] == ["BUY", "SELL"]
    assert all(row.price == Decimal("100") for row in rows)
    assert all(row.amount_krw == (100 if market == "KR" else 130000) for row in rows)
    assert all(row.exchange_rate == (None if market == "KR" else Decimal("1300")) for row in rows)
    assert [row.fee for row in rows] == ([0, 0] if market == "KR" else [91, 91])
    assert [row.tax for row in rows] == [0, 0]
    assert Account.query.filter_by(user_id=1).one().balance == (1000000 if market == "KR" else 999818)
    assert MarketHolding.query.one().quantity == 0
    assert [row.transaction_type for row in LedgerTransaction.query.order_by(LedgerTransaction.ledger_transaction_id)] == ["STOCK_BUY", "STOCK_SELL"]
    assert calls["session"] == [Market(market), Market(market)]
    assert len(calls["fx"]) == (0 if market == "KR" else 2)


def test_validated_order_still_rolls_back_if_ledger_fails(client, auth, listing, monkeypatch):
    listing[0]()
    def fail(**kwargs):
        raise RuntimeError("synthetic ledger failure")
    monkeypatch.setattr(investment_service, "create_ledger", fail)
    assert order(client, auth).status_code == 500
    unchanged()
    assert MarketAsset.query.count() == 0
