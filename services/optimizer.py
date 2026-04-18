"""Markowitz mean-variance portfolio optimizer using scipy."""
import logging

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


async def optimizar_cartera(
    posiciones: list[dict],
    perfil: dict,
    objetivo: str = "sharpe",
) -> dict:
    """Compute optimal portfolio weights using Markowitz mean-variance optimization.

    Args:
        posiciones: List of dicts with keys symbol, qty, precio, valor.
        perfil: Investment profile dict with risk_tolerance (1-10) and max_position_pct (0-100).
        objetivo: Optimization objective — 'sharpe' (default) or 'min_vol'.

    Returns:
        dict with keys: optimal_weights (dict symbol->weight), expected_return_annual,
                        expected_vol_annual, expected_sharpe, current_weights (dict),
                        operations (list of dicts with symbol, current_pct, target_pct, delta_pct).

    Raises:
        ValueError: If optimization fails or fewer than 2 valid symbols found.
    """
    try:
        symbols = [p["symbol"] for p in posiciones]
        valores = {p["symbol"]: float(p["valor"]) for p in posiciones}
        total_valor = sum(valores.values())

        # Download 1 year of historical data
        raw = yf.download(symbols, period="1y", auto_adjust=True, progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"]
        else:
            close = raw[["Close"]].rename(columns={"Close": symbols[0]})

        # Filter symbols with data
        valid_symbols = [
            s for s in symbols if s in close.columns and not close[s].dropna().empty
        ]
        if len(valid_symbols) < 2:
            raise ValueError("Se necesitan al menos 2 símbolos con datos para optimizar")

        df = close[valid_symbols].dropna()
        log_returns = np.log(df / df.shift(1)).dropna()

        mu = log_returns.mean().values * 252  # annualized
        cov = log_returns.cov().values * 252   # annualized covariance

        n = len(valid_symbols)
        max_pos = float(perfil.get("max_position_pct", 25)) / 100
        risk_tolerance = int(perfil.get("risk_tolerance", 5))

        rf = 0.05  # annual risk-free rate

        def neg_sharpe(w):
            port_ret = float(np.dot(w, mu))
            port_vol = float(np.sqrt(w @ cov @ w))
            return -(port_ret - rf) / port_vol if port_vol > 0 else 0

        def portfolio_vol(w):
            return float(np.sqrt(w @ cov @ w))

        objective_fn = neg_sharpe if objetivo == "sharpe" else portfolio_vol

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        # Additional volatility constraint for low risk tolerance
        if risk_tolerance < 4:
            constraints.append({
                "type": "ineq",
                "fun": lambda w: 0.15 - portfolio_vol(w),
            })

        bounds = [(0.05, max_pos)] * n
        w0 = np.full(n, 1.0 / n)

        result = minimize(
            objective_fn,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-9},
        )

        if not result.success:
            raise ValueError(f"Optimización no convergió: {result.message}")

        w_opt = result.x
        w_opt = np.clip(w_opt, 0, 1)
        w_opt = w_opt / w_opt.sum()

        expected_return = float(np.dot(w_opt, mu))
        expected_vol = float(np.sqrt(w_opt @ cov @ w_opt))
        expected_sharpe = (expected_return - rf) / expected_vol if expected_vol > 0 else 0.0

        # Current weights
        current_w = {s: valores.get(s, 0) / total_valor for s in valid_symbols}

        # Operations needed
        operations = []
        for s, w_target in zip(valid_symbols, w_opt):
            w_current = current_w.get(s, 0)
            delta = float(w_target) - float(w_current)
            operations.append({
                "symbol": s,
                "current_pct": round(w_current * 100, 2),
                "target_pct": round(float(w_target) * 100, 2),
                "delta_pct": round(delta * 100, 2),
            })

        return {
            "optimal_weights": {s: round(float(w), 4) for s, w in zip(valid_symbols, w_opt)},
            "expected_return_annual": round(expected_return * 100, 2),
            "expected_vol_annual": round(expected_vol * 100, 2),
            "expected_sharpe": round(expected_sharpe, 3),
            "current_weights": {s: round(float(v), 4) for s, v in current_w.items()},
            "operations": operations,
        }
    except Exception as e:
        logger.exception("Error en optimizar_cartera: %s", e)
        raise


def formatear_rebalanceo_para_telegram(resultado: dict) -> str:
    """Format optimization result for Telegram Markdown.

    Args:
        resultado: Dict returned by optimizar_cartera.

    Returns:
        str: Telegram-compatible Markdown string.

    Raises:
        KeyError: If required keys are missing.
    """
    try:
        lines = [
            "⚖️ *Rebalanceo óptimo (Markowitz)*\n",
            f"• Retorno esperado anual: {resultado['expected_return_annual']:+.2f}%",
            f"• Volatilidad anual: {resultado['expected_vol_annual']:.2f}%",
            f"• Sharpe esperado: {resultado['expected_sharpe']:.3f}\n",
            "*Distribución objetivo:*",
        ]

        for op in sorted(resultado["operations"], key=lambda x: -x["target_pct"]):
            arrow = "↑" if op["delta_pct"] > 0.5 else ("↓" if op["delta_pct"] < -0.5 else "→")
            lines.append(
                f"  {arrow} `{op['symbol']}`: {op['current_pct']:.1f}% → {op['target_pct']:.1f}% "
                f"({op['delta_pct']:+.1f}%)"
            )

        lines.append(
            "\n⚠️ *Disclaimer:* Esta optimización es informativa y no constituye asesoramiento "
            "financiero regulado. Consulta a un asesor certificado antes de operar."
        )

        return "\n".join(lines)
    except Exception as e:
        logger.exception("Error en formatear_rebalanceo_para_telegram: %s", e)
        raise
