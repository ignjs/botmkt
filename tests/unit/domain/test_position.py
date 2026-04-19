from decimal import Decimal

import pytest

from domain.entities.position import Position
from domain.exceptions import InvalidPriceError, InvalidQuantityError
from domain.value_objects.money import Money
from domain.value_objects.symbol import Symbol


def _pos() -> Position:
    return Position(Symbol("AAPL"), Decimal("10"), Money(Decimal("200")))


def test_position_calculates_pnl_correctly() -> None:
    p = _pos()
    pnl = p.current_pnl(Money(Decimal("220")))
    assert pnl.amount == Decimal("200")


def test_position_rejects_zero_quantity() -> None:
    with pytest.raises(InvalidQuantityError):
        Position(Symbol("AAPL"), Decimal("0"), Money(Decimal("200")))


def test_position_rejects_negative_quantity() -> None:
    with pytest.raises(InvalidQuantityError):
        Position(Symbol("AAPL"), Decimal("-1"), Money(Decimal("200")))


def test_stop_triggered_at_exact_stop_price() -> None:
    p = Position(Symbol("AAPL"), Decimal("1"), Money(Decimal("100")), stop_loss=Money(Decimal("90")))
    assert p.is_stop_triggered(Money(Decimal("90"))) is True


def test_stop_not_triggered_above_stop_price() -> None:
    p = Position(Symbol("AAPL"), Decimal("1"), Money(Decimal("100")), stop_loss=Money(Decimal("90")))
    assert p.is_stop_triggered(Money(Decimal("91"))) is False


def test_stop_not_triggered_when_no_stop_set() -> None:
    p = _pos()
    assert p.is_stop_triggered(Money(Decimal("50"))) is False


def test_merge_calculates_weighted_average_price() -> None:
    p = _pos()
    merged = p.merge_with_new_purchase(Decimal("5"), Money(Decimal("220")))
    assert merged.avg_buy_price.amount == Decimal("206.67")


def test_merge_accumulates_quantity() -> None:
    p = _pos()
    merged = p.merge_with_new_purchase(Decimal("5"), Money(Decimal("220")))
    assert merged.quantity == Decimal("15")


def test_stop_loss_must_be_below_entry_price() -> None:
    with pytest.raises(InvalidPriceError):
        Position(Symbol("AAPL"), Decimal("1"), Money(Decimal("100")), stop_loss=Money(Decimal("100")))
