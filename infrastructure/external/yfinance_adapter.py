import yfinance as yf

from application.ports.market_data_port import MarketDataPort


class YFinanceAdapter(MarketDataPort):
    """Adapter de mercado basado en yfinance."""

    async def get_price(self, symbol: str) -> float:
        hist = yf.Ticker(symbol).history(period="1d")
        if hist.empty:
            raise ValueError(f"Sin datos para {symbol}")
        return float(hist["Close"].iloc[-1])
