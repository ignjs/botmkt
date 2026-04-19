import pytest

from application.use_cases.remove_position import RemovePositionUseCase


@pytest.mark.asyncio
async def test_remove_calls_repository(mock_position_repo) -> None:
    use_case = RemovePositionUseCase(mock_position_repo)
    await use_case.execute(1, "AAPL")
    assert mock_position_repo.delete.await_count == 1
