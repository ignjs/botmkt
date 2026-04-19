import pytest

from application.use_cases.get_portfolio import GetPortfolioUseCase


@pytest.mark.asyncio
async def test_get_portfolio_returns_list(mock_position_repo) -> None:
    use_case = GetPortfolioUseCase(mock_position_repo)
    result = await use_case.execute(1)
    assert isinstance(result, list)
