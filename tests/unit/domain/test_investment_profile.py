import pytest

from domain.entities.investment_profile import InvestmentProfile
from domain.exceptions import BotMKTError


def _valid_profile() -> dict:
    return {
        "risk_tolerance": 5,
        "investment_horizon": "largo",
        "max_position_pct": 25,
        "max_country_pct": 70,
        "max_sector_pct": 50,
        "max_drawdown_pct": 12,
        "preferred_strategy": "mixta",
        "cash_buffer_pct": 10,
    }


def test_profile_rejects_invalid_risk_tolerance() -> None:
    data = _valid_profile()
    data["risk_tolerance"] = 11
    with pytest.raises(BotMKTError):
        InvestmentProfile(**data)
