"""Risk engine: portfolio metrics computation and Telegram formatting."""
import logging
import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


async def calcular_metricas_cartera(posiciones: list[dict], periodo: str = "1y") -> dict:
    """Compute risk metrics for a portfolio.

    Args:
        posiciones: List of position dicts with keys symbol, qty, precio, valor.
        periodo: yfinance period string (default '1y').

    Returns:
        dict with keys: var_95_pct, var_95_usd, sharpe, max_drawdown_pct, hhi, portfolio_value,
                        symbols_used, symbols_excluded, weights.

    Raises:
        ValueError: If no valid positions remain after filtering.
    """
    try:
        symbols = [p["symbol"] for p in posiciones]
        valores = {p["symbol"]: float(p["valor"]) for p in posiciones}
        total_valor = sum(valores.values())

        # Download all symbols in one call
        raw = yf.download(symbols, period=periodo, auto_adjust=True, progress=False)

        # Handle single vs multiple symbols
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"]
        else:
            # Single symbol: yfinance returns flat DataFrame
            close = raw[["Close"]].rename(columns={"Close": symbols[0]})

        symbols_used = []
        symbols_excluded = []
        close_clean = {}

        for sym in symbols:
            if sym not in close.columns or close[sym].dropna().empty:
                logger.warning("Sin datos para %s, excluyendo", sym)
                symbols_excluded.append(sym)
            else:
                close_clean[sym] = close[sym].dropna()
                symbols_used.append(sym)

        if not symbols_used:
            raise ValueError("No hay símbolos con datos válidos")

        df = pd.DataFrame(close_clean).dropna()

        # Log returns
        log_returns = np.log(df / df.shift(1)).dropna()

        # Weights by market value (only symbols_used)
        w = np.array([valores.get(s, 0) for s in symbols_used], dtype=float)
        w = w / w.sum()

        # Portfolio returns
        port_returns = log_returns[symbols_used].values @ w

        mu = port_returns.mean()
        sigma = port_returns.std()

        rf_daily = 0.05 / 252

        # VaR 95% parametric 1-day
        var_95_pct = -(mu - 1.645 * sigma) * 100
        var_95_usd = var_95_pct / 100 * total_valor

        # Sharpe annualized
        sharpe = ((mu - rf_daily) / sigma * np.sqrt(252)) if sigma > 0 else 0.0

        # Maximum Drawdown
        cum_returns = np.exp(np.cumsum(port_returns))
        rolling_max = np.maximum.accumulate(cum_returns)
        drawdowns = (cum_returns - rolling_max) / rolling_max
        max_drawdown_pct = float(np.min(drawdowns)) * 100

        # HHI (Herfindahl-Hirschman Index)
        hhi = float(np.sum((w * 100) ** 2))

        return {
            "var_95_pct": round(var_95_pct, 2),
            "var_95_usd": round(var_95_usd, 2),
            "sharpe": round(float(sharpe), 3),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "hhi": round(hhi, 1),
            "portfolio_value": round(total_valor, 2),
            "symbols_used": symbols_used,
            "symbols_excluded": symbols_excluded,
            "weights": {s: round(float(wi), 4) for s, wi in zip(symbols_used, w)},
        }
    except Exception as e:
        logger.exception("Error en calcular_metricas_cartera: %s", e)
        raise


def formatear_metricas_para_telegram(metricas: dict) -> str:
    """Format portfolio metrics for Telegram Markdown display.

    Args:
        metricas: Dict returned by calcular_metricas_cartera.

    Returns:
        str: Markdown-formatted string ready for Telegram.

    Raises:
        KeyError: If required metric keys are missing.
    """
    try:
        sharpe = metricas["sharpe"]
        hhi = metricas["hhi"]

        sharpe_emoji = "🟢" if sharpe > 1 else ("🟡" if sharpe >= 0 else "🔴")
        hhi_emoji = "🟢" if hhi < 1500 else ("🟡" if hhi <= 2500 else "🔴")

        excluded_note = ""
        if metricas.get("symbols_excluded"):
            excluded_note = f"\n⚠️ Sin datos: {', '.join(metricas['symbols_excluded'])}"

        return (
            "📊 *Métricas de Riesgo*\n"
            f"• VaR 95% 1d: {metricas['var_95_pct']:+.2f}% (${metricas['var_95_usd']:,.0f})\n"
            f"• Sharpe anual: {sharpe:.3f} {sharpe_emoji}\n"
            f"• Max Drawdown: {metricas['max_drawdown_pct']:.2f}%\n"
            f"• HHI concentración: {hhi:.0f} {hhi_emoji}"
            f"{excluded_note}"
        )
    except Exception as e:
        logger.exception("Error en formatear_metricas_para_telegram: %s", e)
        raise
