from dataclasses import dataclass
from typing import Literal

from domain.exceptions import BotMKTError

InvestmentHorizon = Literal["corto", "mediano", "largo"]
Strategy = Literal["growth", "dividendos", "valor", "mixta"]


@dataclass
class InvestmentProfile:
    """Preferencias y límites de riesgo del inversionista."""

    risk_tolerance: int
    investment_horizon: InvestmentHorizon
    max_position_pct: float
    max_country_pct: float
    max_sector_pct: float
    max_drawdown_pct: float
    preferred_strategy: Strategy
    cash_buffer_pct: float

    def __post_init__(self) -> None:
        if not 1 <= self.risk_tolerance <= 10:
            raise BotMKTError("risk_tolerance debe estar entre 1 y 10")

        for field_name in (
            "max_position_pct",
            "max_country_pct",
            "max_sector_pct",
            "max_drawdown_pct",
            "cash_buffer_pct",
        ):
            value = getattr(self, field_name)
            if not 0 <= value <= 100:
                raise BotMKTError(f"{field_name} debe estar entre 0 y 100")

    @property
    def is_conservative(self) -> bool:
        return self.risk_tolerance <= 3

    @property
    def is_aggressive(self) -> bool:
        return self.risk_tolerance >= 8
