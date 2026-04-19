"""Integration tests for services/alert_engine.py — E2."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_position(symbol: str, stop_loss=None) -> dict:
    return {
        "symbol": symbol,
        "quantity": 10,
        "avg_buy_price": 200.0,
        "stop_loss": stop_loss,
        "atr": None,
    }


def _make_metrics(price: float, rsi: float = 50.0, vol_zscore: float = 0.5) -> dict:
    return {"price": price, "rsi": rsi, "vol_zscore": vol_zscore}


@pytest.mark.asyncio
async def test_stop_loss_alert_sent():
    """When price falls below stop_loss, an alert should be sent."""
    from services.alert_engine import check_all_positions

    position = _make_position("AAPL", stop_loss=190.0)
    metrics = _make_metrics(price=185.0)  # below stop_loss

    mock_bot = AsyncMock()

    with (
        patch("services.alert_engine.get_all_users_with_positions", new=AsyncMock(return_value=[{"telegram_user_id": 123}])),
        patch("services.alert_engine.get_positions", new=AsyncMock(return_value=[position])),
        patch("services.alert_engine._get_metrics_async", new=AsyncMock(return_value=metrics)),
        patch("services.alert_engine.was_alert_sent_recently", new=AsyncMock(return_value=False)),
        patch("services.alert_engine.record_alert_sent", new=AsyncMock()),
    ):
        await check_all_positions(mock_bot)

    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args
    assert call_kwargs.kwargs["chat_id"] == 123
    assert "Stop-Loss" in call_kwargs.kwargs["text"]


@pytest.mark.asyncio
async def test_rsi_oversold_alert():
    """RSI < 30 should trigger an oversold alert."""
    from services.alert_engine import check_all_positions

    position = _make_position("MSFT", stop_loss=None)
    metrics = _make_metrics(price=300.0, rsi=25.0)

    mock_bot = AsyncMock()

    with (
        patch("services.alert_engine.get_all_users_with_positions", new=AsyncMock(return_value=[{"telegram_user_id": 456}])),
        patch("services.alert_engine.get_positions", new=AsyncMock(return_value=[position])),
        patch("services.alert_engine._get_metrics_async", new=AsyncMock(return_value=metrics)),
        patch("services.alert_engine.was_alert_sent_recently", new=AsyncMock(return_value=False)),
        patch("services.alert_engine.record_alert_sent", new=AsyncMock()),
    ):
        await check_all_positions(mock_bot)

    mock_bot.send_message.assert_called_once()
    assert "Sobreventa" in mock_bot.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_no_duplicate_alert_within_cooldown():
    """An alert should NOT be sent if already sent within the cooldown window."""
    from services.alert_engine import check_all_positions

    position = _make_position("AAPL", stop_loss=190.0)
    metrics = _make_metrics(price=185.0)

    mock_bot = AsyncMock()

    with (
        patch("services.alert_engine.get_all_users_with_positions", new=AsyncMock(return_value=[{"telegram_user_id": 123}])),
        patch("services.alert_engine.get_positions", new=AsyncMock(return_value=[position])),
        patch("services.alert_engine._get_metrics_async", new=AsyncMock(return_value=metrics)),
        patch("services.alert_engine.was_alert_sent_recently", new=AsyncMock(return_value=True)),  # already sent
        patch("services.alert_engine.record_alert_sent", new=AsyncMock()),
    ):
        await check_all_positions(mock_bot)

    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_volume_spike_alert():
    """Volume z-score > 2 should trigger a volume spike alert."""
    from services.alert_engine import check_all_positions

    position = _make_position("GOOG", stop_loss=None)
    metrics = _make_metrics(price=150.0, rsi=50.0, vol_zscore=3.5)

    mock_bot = AsyncMock()

    with (
        patch("services.alert_engine.get_all_users_with_positions", new=AsyncMock(return_value=[{"telegram_user_id": 789}])),
        patch("services.alert_engine.get_positions", new=AsyncMock(return_value=[position])),
        patch("services.alert_engine._get_metrics_async", new=AsyncMock(return_value=metrics)),
        patch("services.alert_engine.was_alert_sent_recently", new=AsyncMock(return_value=False)),
        patch("services.alert_engine.record_alert_sent", new=AsyncMock()),
    ):
        await check_all_positions(mock_bot)

    mock_bot.send_message.assert_called_once()
    assert "Volumen" in mock_bot.send_message.call_args.kwargs["text"]
