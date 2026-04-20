import pytest

from services.broker_service import get_account_info, get_open_positions, place_order


class _MockEnumValue:
    def __init__(self, v):
        self.value = v


class DummyOrder:
    id = "abc123"
    symbol = "AAPL"
    qty = "5"
    side = _MockEnumValue("buy")
    status = _MockEnumValue("filled")
    filled_avg_price = "210.20"


class DummyAccount:
    status = "ACTIVE"
    equity = "10000"
    cash = "5000"
    buying_power = "20000"


class DummyPosition:
    def __init__(self, symbol, qty, avg_entry_price, market_value, unrealized_pl):
        self.symbol = symbol
        self.qty = qty
        self.avg_entry_price = avg_entry_price
        self.market_value = market_value
        self.unrealized_pl = unrealized_pl


class DummyClient:
    def submit_order(self, order_request):
        from alpaca.trading.requests import MarketOrderRequest

        assert isinstance(order_request, MarketOrderRequest)
        return DummyOrder()

    def get_account(self):
        return DummyAccount()

    def get_all_positions(self):
        return [DummyPosition("AAPL", "5", "200", "1050", "50")]


@pytest.mark.asyncio
async def test_place_order_with_mocked_alpaca(monkeypatch):
    monkeypatch.setattr("services.broker_service._build_client", lambda: DummyClient())
    result = await place_order("AAPL", 5, "buy")
    assert result["id"] == "abc123"
    assert result["symbol"] == "AAPL"
    assert result["qty"] == 5.0


@pytest.mark.asyncio
async def test_get_account_info_with_mocked_alpaca(monkeypatch):
    monkeypatch.setattr("services.broker_service._build_client", lambda: DummyClient())
    result = await get_account_info()
    assert result["status"] == "ACTIVE"
    assert result["equity"] == 10000.0


@pytest.mark.asyncio
async def test_get_open_positions_with_mocked_alpaca(monkeypatch):
    monkeypatch.setattr("services.broker_service._build_client", lambda: DummyClient())
    result = await get_open_positions()
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"
