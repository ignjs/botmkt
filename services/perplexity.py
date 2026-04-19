import json
import logging
import re
from typing import Dict, Optional

from openai import OpenAI

from config import Config
from utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=Config.PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai"
)

PROMPT_CONFIG = {
    "stock_analysis": {"temperature": 0.2, "max_tokens": 500},
    "portfolio_analysis": {"temperature": 0.2, "max_tokens": 500},
    "portfolio_rules": {"temperature": 0.1, "max_tokens": 450},
    "weekly_execution_plan": {"temperature": 0.15, "max_tokens": 650},
    "telegram_brief": {"temperature": 0.1, "max_tokens": 300},
}

_REC_PATTERN = re.compile(
    r'\b(comprar|vender|mantener|aumentar|reducir)\b',
    re.IGNORECASE,
)
_CONFIDENCE_PATTERN = re.compile(
    r'riesgo[:\s]+(\d{1,2})/10',
    re.IGNORECASE,
)


def _chat(prompt: str, temperature: float = 0.2, max_tokens: int = 500) -> str:
    if not Config.PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY no está configurada")

    completion = client.chat.completions.create(
        model="sonar-pro",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return completion.choices[0].message.content or ""


def _render_json(payload: Dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _extract_recommendation(text: str) -> Optional[str]:
    """Parse the first recognized recommendation keyword from an AI response."""
    match = _REC_PATTERN.search(text)
    if not match:
        return None
    word = match.group(1).lower()
    # Normalize synonyms
    if word in ("aumentar",):
        return "comprar"
    if word in ("reducir",):
        return "vender"
    return word


def _extract_confidence(text: str) -> Optional[int]:
    """Parse the risk/confidence score (1-10) from an AI response."""
    match = _CONFIDENCE_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


def build_stock_analysis_prompt(symbol: str, indicadores: dict) -> str:
    stock_table = (
        f"| Precio | ${indicadores['precio_actual']}\n"
        f"| Cambio 24h | {indicadores['cambio_24h']}%\n"
        f"| RSI | {indicadores['rsi']}\n"
        f"| MACD | {indicadores['macd']}"
    )

    position_context = "Sin datos de posición en cartera."
    if "position_qty" in indicadores and "avg_buy_price" in indicadores:
        position_context = (
            "Datos de mi posición en cartera:\n"
            f"| Cantidad | {indicadores['position_qty']}\n"
            f"| Precio compra promedio | ${indicadores['avg_buy_price']}\n"
            f"| Valor invertido | ${indicadores.get('invested_value', 0):,.2f}\n"
            f"| Valor actual | ${indicadores.get('market_value', 0):,.2f}\n"
            f"| P/L posición | ${indicadores.get('position_pl_abs', 0):,.2f} "
            f"({indicadores.get('position_pl_pct', 0):+.2f}%)"
        )

    return load_prompt(
        "stock_analysis",
        symbol=symbol,
        stock_table=stock_table,
        position_context=position_context,
    )


def build_stock_analysis_prompt_with_backtest(
    symbol: str, indicadores: dict, backtest_summary: str
) -> str:
    """Build stock analysis prompt with backtest context included."""
    base_prompt = build_stock_analysis_prompt(symbol, indicadores)
    return (
        base_prompt
        + f"\n\nContexto adicional — Backtest histórico RSI+MACD en {symbol}:\n{backtest_summary}"
    )


def build_portfolio_analysis_prompt(tabla_markdown: str) -> str:
    return load_prompt("portfolio_analysis", portfolio_table=tabla_markdown)


def build_portfolio_rules_prompt(profile: dict, diagnosis: dict) -> str:
    return load_prompt(
        "portfolio_rules",
        profile_json=_render_json(profile),
        diagnosis_json=_render_json(diagnosis),
    )


def build_weekly_plan_prompt(profile: dict, diagnosis: dict, previous_plan: str = "") -> str:
    """Build the weekly execution plan prompt.

    Args:
        profile: Investment profile dict.
        diagnosis: Portfolio diagnosis dict.
        previous_plan: Previous week's plan text for memory context.

    Returns:
        str: Rendered prompt string.
    """
    return load_prompt(
        "weekly_execution_plan",
        profile_json=_render_json(profile),
        diagnosis_json=_render_json(diagnosis),
        previous_plan=previous_plan or "Sin plan registrado la semana anterior.",
    )


def build_telegram_brief_prompt(plan_text: str, diagnosis: dict) -> str:
    return load_prompt(
        "telegram_brief",
        plan_text=plan_text,
        portfolio_summary_json=_render_json(diagnosis.get("portfolio_summary", {})),
    )


async def analyze_stock(symbol: str, indicadores: dict) -> str:
    prompt = build_stock_analysis_prompt(symbol, indicadores)
    config = PROMPT_CONFIG["stock_analysis"]
    return _chat(prompt, **config)


async def analyze_portfolio(tabla_markdown: str) -> str:
    prompt = build_portfolio_analysis_prompt(tabla_markdown)
    config = PROMPT_CONFIG["portfolio_analysis"]
    return _chat(prompt, **config)


async def analyze_portfolio_against_rules(profile: dict, diagnosis: dict) -> str:
    prompt = build_portfolio_rules_prompt(profile, diagnosis)
    config = PROMPT_CONFIG["portfolio_rules"]
    return _chat(prompt, **config)


async def generate_weekly_plan_text(
    profile: dict, diagnosis: dict, previous_plan: str = ""
) -> str:
    """Generate the weekly execution plan text via AI.

    Args:
        profile: Investment profile dict.
        diagnosis: Portfolio diagnosis dict.
        previous_plan: Previous week's plan text for memory context.

    Returns:
        str: AI-generated plan text.
    """
    prompt = build_weekly_plan_prompt(profile, diagnosis, previous_plan)
    config = PROMPT_CONFIG["weekly_execution_plan"]
    return _chat(prompt, **config)


async def generate_telegram_plan_summary(plan_text: str, diagnosis: dict) -> str:
    prompt = build_telegram_brief_prompt(plan_text, diagnosis)
    config = PROMPT_CONFIG["telegram_brief"]
    return _chat(prompt, **config)


async def analyze_stock_with_sentiment(
    symbol: str, indicadores: dict
) -> tuple[str, Optional[int]]:
    """Analyze a stock and extract a sentiment score 1-10.

    Args:
        symbol: Ticker symbol.
        indicadores: Market data dict.

    Returns:
        tuple[str, Optional[int]]: (analysis_text, sentiment_score or None).

    Raises:
        Exception: On API failure.
    """
    try:
        prompt = build_stock_analysis_prompt(symbol, indicadores)
        sentiment_prompt = (
            prompt + "\n\nAl final de tu respuesta, en una línea separada, escribe exactamente: "
            "SENTIMIENTO: X/10 donde X es un número del 1 al 10 que refleje el sentimiento "
            "del mercado (1=muy negativo, 10=muy positivo), basado en 3 titulares recientes o indicadores técnicos."
        )
        config = PROMPT_CONFIG["stock_analysis"]
        response = _chat(sentiment_prompt, **config)

        # Parse sentiment score (matches 1-9 or 10)
        sentiment_score = None
        match = re.search(r'SENTIMIENTO:\s*(10|[1-9])/10', response, re.IGNORECASE)
        if match:
            sentiment_score = int(match.group(1))

        return response, sentiment_score
    except Exception as e:
        logger.exception("Error en analyze_stock_with_sentiment: %s", e)
        raise


async def analyze_stock_and_record(
    telegram_user_id: int,
    symbol: str,
    indicadores: dict,
    backtest_summary: Optional[str] = None,
) -> str:
    """Analyze a stock, record the AI recommendation to DB, and return the analysis text.

    Args:
        telegram_user_id: Telegram user ID used to save the recommendation.
        symbol: Ticker symbol.
        indicadores: Market data dict.
        backtest_summary: Optional backtest context string to include in the prompt.

    Returns:
        str: AI analysis text.
    """
    if backtest_summary:
        prompt = build_stock_analysis_prompt_with_backtest(symbol, indicadores, backtest_summary)
    else:
        prompt = build_stock_analysis_prompt(symbol, indicadores)

    config = PROMPT_CONFIG["stock_analysis"]
    response = _chat(prompt, **config)

    # Save recommendation to DB (non-blocking on failure)
    try:
        recommendation = _extract_recommendation(response)
        confidence = _extract_confidence(response)
        price = float(indicadores.get("precio_actual", 0))
        if recommendation and price > 0:
            from db import save_ai_recommendation
            await save_ai_recommendation(
                telegram_user_id=telegram_user_id,
                symbol=symbol,
                recommendation=recommendation,
                confidence=confidence,
                price_at_recommendation=price,
            )
    except Exception as exc:
        logger.warning("No se pudo guardar recomendación IA para %s: %s", symbol, exc)

    return response

