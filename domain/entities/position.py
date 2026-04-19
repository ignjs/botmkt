from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from domain.exceptions import InvalidPriceError, InvalidQuantityError
from domain.value_objects.money import Money
from domain.value_objects.symbol import Symbol


@dataclass
class Position:
    """Entidad de posición de cartera."""

    symbol: Symbol
    quantity: Decimal
    avg_buy_price: Money
    stop_loss: Money | None = None
    atr: Decimal | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise InvalidQuantityError(
                f"La cantidad debe ser positiva, recibido: {self.quantity}"
            )
        if self.avg_buy_price.amount <= 0:
            raise InvalidPriceError("El precio de compra debe ser mayor a cero")
        if self.stop_loss and self.stop_loss.amount >= self.avg_buy_price.amount:
            raise InvalidPriceError("El stop-loss debe ser menor al precio de entrada")

    def current_pnl(self, current_price: Money) -> Money:
        return Money(
            (current_price.amount - self.avg_buy_price.amount) * self.quantity,
            self.avg_buy_price.currency,
        )

    def pnl_pct(self, current_price: Money) -> Decimal:
        return (
            (current_price.amount - self.avg_buy_price.amount)
            / self.avg_buy_price.amount
            * 100
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def market_value(self, current_price: Money) -> Money:
        return current_price * self.quantity

    def is_stop_triggered(self, current_price: Money) -> bool:
        if self.stop_loss is None:
            return False
        return current_price.amount <= self.stop_loss.amount

    def merge_with_new_purchase(self, new_qty: Decimal, new_price: Money) -> "Position":
        if new_qty <= 0:
            raise InvalidQuantityError("La cantidad adicional debe ser positiva")
        if new_price.amount <= 0:
            raise InvalidPriceError("El precio de compra debe ser mayor a cero")

        total_qty = self.quantity + new_qty
        weighted_avg = (
            self.avg_buy_price.amount * self.quantity + new_price.amount * new_qty
        ) / total_qty
        weighted_avg = weighted_avg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Position(
            symbol=self.symbol,
            quantity=total_qty,
            avg_buy_price=Money(weighted_avg, self.avg_buy_price.currency),
            stop_loss=self.stop_loss,
            atr=self.atr,
        )
