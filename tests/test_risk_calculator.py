import pandas as pd
import pytest

from services.risk_calculator import calculate_atr_stop


@pytest.mark.asyncio
async def test_calculate_atr_stop_returns_expected_keys(mocker):
    highs = [10 + i * 0.4 for i in range(30)]
    lows = [9 + i * 0.35 for i in range(30)]
    closes = [9.5 + i * 0.38 for i in range(30)]
    fake_hist = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})

    fake_ticker = mocker.Mock()
    fake_ticker.history.return_value = fake_hist
    mocker.patch("services.risk_calculator.yf.Ticker", return_value=fake_ticker)

    result = await calculate_atr_stop("AAPL", 210.0, multiplier=2.0)

    assert set(result.keys()) == {"atr", "stop_loss", "stop_pct"}
    assert result["atr"] > 0
    assert result["stop_loss"] < 210.0
    assert result["stop_pct"] < 0
