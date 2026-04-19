"""Unit tests for services/broker_service.py — E5."""
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_api():
    api = MagicMock()
    order = MagicMock()
    order.id = "test-order-123"
    order.symbol = "AAPL"
    order.qty = "5"
    order.side = "buy"
    order.status = "filled"
    order.filled_avg_price = "210.50"
    api.submit_order.return_value = order

    account = MagicMock()
    account.cash = "10000.00"
    account.portfolio_value = "50000.00"
    account.buying_power = "20000.00"
    account.currency = "USD"
    api.get_account.return_value = account

    position = MagicMock()
    position.symbol = "AAPL"
    position.qty = "10"
    position.avg_entry_price = "200.00"
    position.current_price = "210.00"
    position.unrealized_pl = "100.00"
    position.unrealized_plpc = "0.05"
    api.list_positions.return_value = [position]

    trade = MagicMock()
    trade.price = 210.20
    api.get_latest_trade.return_value = trade

    return api


@pytest.mark.asyncio
async def test_place_order_buy():
    """place_order should call submit_order and return a valid result dict."""
    from services.broker_service import place_order

    mock_api = _make_mock_api()

    with patch("services.broker_service._get_alpaca_client", return_value=mock_api):
        result = await place_order("AAPL", 5, "buy")

    assert result["symbol"] == "AAPL"
    assert result["side"] == "buy"
    assert result["status"] == "filled"
    assert result["filled_avg_price"] == pytest.approx(210.50)
    mock_api.submit_order.assert_called_once_with(
        symbol="AAPL", qty=5, side="buy", type="market", time_in_force="day"
    )


@pytest.mark.asyncio
async def test_place_order_invalid_qty():
    """place_order should raise ValueError for non-positive quantity."""
    from services.broker_service import place_order

    with pytest.raises(ValueError, match="qty debe ser mayor a 0"):
        await place_order("AAPL", 0, "buy")


@pytest.mark.asyncio
async def test_place_order_invalid_side():
    """place_order should raise ValueError for unknown side."""
    from services.broker_service import place_order

    with pytest.raises(ValueError, match="side debe ser"):
        await place_order("AAPL", 5, "hold")


@pytest.mark.asyncio
async def test_get_account_info():
    """get_account_info should return a dict with cash and portfolio_value."""
    from services.broker_service import get_account_info

    mock_api = _make_mock_api()

    with patch("services.broker_service._get_alpaca_client", return_value=mock_api):
        result = await get_account_info()

    assert result["cash"] == pytest.approx(10000.0)
    assert result["portfolio_value"] == pytest.approx(50000.0)
    assert result["mode"] in ("paper", "live")


@pytest.mark.asyncio
async def test_get_open_positions():
    """get_open_positions should return a list of position dicts."""
    from services.broker_service import get_open_positions

    mock_api = _make_mock_api()

    with patch("services.broker_service._get_alpaca_client", return_value=mock_api):
        positions = await get_open_positions()

    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"
    assert positions[0]["qty"] == pytest.approx(10.0)
