import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.investment_profile import PROFILE_FLOW_KEY, investment_profile_handler


SAMPLE_PROFILE = {
    "risk_tolerance": 5,
    "investment_horizon": "largo",
    "max_position_pct": 25,
    "max_country_pct": 70,
    "max_sector_pct": 45,
    "max_drawdown_pct": 12,
    "preferred_strategy": "mixta",
    "cash_buffer_pct": 10,
}


class DummyMessage:
    def __init__(self, text: str):
        self.text = text
        self.replies = []

    async def reply_text(self, text: str, parse_mode=None):
        self.replies.append({"text": text, "parse_mode": parse_mode})


class DummyContext:
    def __init__(self):
        self.user_data = {}


class InvestmentProfileHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_profile_is_returned_and_offers_update(self):
        update = SimpleNamespace(
            message=DummyMessage("/perfil"),
            effective_user=SimpleNamespace(id=12345),
        )
        context = DummyContext()

        with patch(
            "handlers.investment_profile.get_investment_profile",
            new=AsyncMock(return_value=SAMPLE_PROFILE),
        ):
            await investment_profile_handler(update, context)

        self.assertEqual(context.user_data[PROFILE_FLOW_KEY]["mode"], "confirm_update")
        self.assertIn("Ya existe un perfil asociado", update.message.replies[0]["text"])
        self.assertIn("Tu perfil de inversión", update.message.replies[0]["text"])

    async def test_missing_profile_starts_questionnaire(self):
        update = SimpleNamespace(
            message=DummyMessage("/perfil"),
            effective_user=SimpleNamespace(id=12345),
        )
        context = DummyContext()

        with patch(
            "handlers.investment_profile.get_investment_profile",
            new=AsyncMock(return_value=None),
        ):
            await investment_profile_handler(update, context)

        self.assertEqual(context.user_data[PROFILE_FLOW_KEY]["mode"], "questionnaire")
        self.assertEqual(context.user_data[PROFILE_FLOW_KEY]["step"], 0)
        self.assertIn("Vamos a crear tu perfil", update.message.replies[0]["text"])

    async def test_actualizar_response_starts_edit_questionnaire(self):
        update = SimpleNamespace(
            message=DummyMessage("actualizar"),
            effective_user=SimpleNamespace(id=12345),
        )
        context = DummyContext()
        context.user_data[PROFILE_FLOW_KEY] = {
            "mode": "confirm_update",
            "existing_profile": SAMPLE_PROFILE,
        }

        await investment_profile_handler(update, context)

        self.assertEqual(context.user_data[PROFILE_FLOW_KEY]["mode"], "questionnaire")
        self.assertIn("Vamos a actualizar tu perfil actual", update.message.replies[0]["text"])
        self.assertIn("Valor actual", update.message.replies[0]["text"])


if __name__ == "__main__":
    unittest.main()
