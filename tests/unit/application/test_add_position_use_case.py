from decimal import Decimal

import pytest

from application.use_cases.add_position import AddPositionUseCase
from domain.entities.position import Position
from domain.exceptions import InvalidQuantityError, InvalidSymbolError
from domain.value_objects.money import Money
from domain.value_objects.symbol import Symbol


@pytest.mark.asyncio
async def test_adds_new_position_when_none_exists(mock_position_repo) -> None:
    use_case = AddPositionUseCase(mock_position_repo)
    result = await use_case.execute(1, "AAPL", 5, 220)
    assert result.quantity == Decimal("5")


@pytest.mark.asyncio
async def test_merges_with_existing_position(mock_position_repo) -> None:
    mock_position_repo.find_by_symbol.return_value = Position(
        Symbol("AAPL"), Decimal("10"), Money(Decimal("200"))
    )
    use_case = AddPositionUseCase(mock_position_repo)
    result = await use_case.execute(1, "AAPL", 5, 220)
    assert result.quantity == Decimal("15")
    assert result.avg_buy_price.amount == Decimal("206.67")


@pytest.mark.asyncio
async def test_raises_invalid_symbol_for_bad_ticker(mock_position_repo) -> None:
    use_case = AddPositionUseCase(mock_position_repo)
    with pytest.raises(InvalidSymbolError):
        await use_case.execute(1, "***", 1, 1)


@pytest.mark.asyncio
async def test_raises_invalid_quantity_for_zero(mock_position_repo) -> None:
    use_case = AddPositionUseCase(mock_position_repo)
    with pytest.raises(InvalidQuantityError):
        await use_case.execute(1, "AAPL", 0, 200)


@pytest.mark.asyncio
async def test_repository_save_called_once(mock_position_repo) -> None:
    use_case = AddPositionUseCase(mock_position_repo)
    await use_case.execute(1, "AAPL", 1, 200)
    assert mock_position_repo.save.await_count == 1
