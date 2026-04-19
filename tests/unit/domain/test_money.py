from decimal import Decimal

import pytest

from domain.value_objects.money import Money


def test_money_rejects_negative_amount() -> None:
    with pytest.raises(ValueError):
        Money(Decimal("-1"))


def test_money_addition_same_currency() -> None:
    a = Money(Decimal("10"))
    b = Money(Decimal("5"))
    assert (a + b).amount == Decimal("15")
