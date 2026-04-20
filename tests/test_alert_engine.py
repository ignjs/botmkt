from types import SimpleNamespace

import pytest

from services.alert_engine import check_all_positions


@pytest.mark.asyncio
async def test_check_all_positions_sends_stop_loss_alert(monkeypatch):
    sent_messages = []
    recorded = []

    async def _fake_get_positions():
        return [
            {
                "user_id": 1,
                "telegram_user_id": 12345,
                "symbol": "AAPL",
                "quantity": 10,
                "avg_buy_price": 210,
                "stop_loss": 195.4,
                "atr": 7.3,
            }
        ]

    async def _fake_get_price(symbol):
        return {"precio_actual": 192.3, "symbol": symbol}

    async def _fake_recent(*args, **kwargs):
        return False

    async def _fake_record(user_id, symbol, alert_type):
        recorded.append((user_id, symbol, alert_type))

    async def _fake_technicals(symbol):
        return {"rsi": 50.0, "volume": 100.0, "volume_mean": 100.0, "volume_std": 1.0}

    class FakeBot:
        async def send_message(self, chat_id, text, parse_mode=None):
            sent_messages.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})

    monkeypatch.setattr("services.alert_engine.get_positions_for_alerting", _fake_get_positions)
    monkeypatch.setattr("services.alert_engine.get_price", _fake_get_price)
    monkeypatch.setattr("services.alert_engine.was_alert_sent_recently", _fake_recent)
    monkeypatch.setattr("services.alert_engine.record_sent_alert", _fake_record)
    monkeypatch.setattr("services.alert_engine._fetch_symbol_technicals", _fake_technicals)

    await check_all_positions(FakeBot())

    assert len(sent_messages) == 1
    assert "Stop-Loss alcanzado" in sent_messages[0]["text"]
    assert sent_messages[0]["chat_id"] == 12345
    assert recorded == [(1, "AAPL", "stop_loss")]
