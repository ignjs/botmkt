from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Money:
    """Value object monetario con moneda explícita."""

    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if self.amount < 0:
            raise ValueError("El monto no puede ser negativo")

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __mul__(self, factor: Decimal | int | float) -> "Money":
        return Money(self.amount * Decimal(str(factor)), self.currency)

    def _assert_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"No se pueden operar monedas distintas: {self.currency} vs {other.currency}"
            )

    def format(self) -> str:
        return f"${self.amount:,.2f}"
