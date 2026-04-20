import pytest

from domain.exceptions import InvalidStrategyError
from handlers.compare_handler import compare_handler
from handlers.screener_handler import screener_handler


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.replies = []

    async def reply_text(self, text, parse_mode=None):
        self.replies.append((text, parse_mode))


class FakeUpdate:
    def __init__(self, text: str):
        self.message = FakeMessage(text)


class FakeContext:
    pass


@pytest.mark.asyncio
async def test_screener_invalid_strategy_raises():
    update = FakeUpdate("/screener invalida chile")
    with pytest.raises(InvalidStrategyError):
        await screener_handler(update, FakeContext())


@pytest.mark.asyncio
async def test_compare_invalid_type_returns_help():
    update = FakeUpdate("/comparar AAPL MSFT raro 12m")
    await compare_handler(update, FakeContext())
    assert any("TIPO inválido" in r[0] for r in update.message.replies)


@pytest.mark.asyncio
async def test_screener_calls_ai(monkeypatch):
    update = FakeUpdate("/screener growth tecnologia")

    async def _fake_call_ai(prompt, max_tokens=None, temperature=0.2):
        return "resultado ok"

    monkeypatch.setattr("handlers.screener_handler.call_ai", _fake_call_ai)
    await screener_handler(update, FakeContext())

    assert any("⏳ Analizando" in r[0] for r in update.message.replies)
    assert any("resultado ok" in r[0] for r in update.message.replies)
