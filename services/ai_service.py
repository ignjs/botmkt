import logging
import re
from typing import Optional, Tuple

import asyncio
from openai import OpenAI

from config.settings import settings
from domain.exceptions import AIAnalysisError
from db import save_ai_recommendation
from services.analysis_prompts import (
    BUILD_PORTFOLIO,
    EARNINGS_BREAKDOWN,
    ENTRY_TIMING,
    FULL_ANALYSIS,
    HEAD_TO_HEAD,
    RISK_ANALYSIS,
    STOCK_SCREENER,
)
from services.perplexity import build_stock_analysis_prompt

logger = logging.getLogger(__name__)

_client = OpenAI(
    api_key=settings.perplexity_api_key or settings.openai_api_key,
    base_url="https://api.perplexity.ai",
)


def parse_recommendation_and_confidence(ai_text: str) -> Tuple[str, Optional[int]]:
    lowered = ai_text.lower()

    if "comprar" in lowered or "aumentar" in lowered:
        recommendation = "comprar"
    elif "vender" in lowered or "reducir" in lowered:
        recommendation = "vender"
    else:
        recommendation = "mantener"

    confidence = None
    match = re.search(r"(10|[1-9])\s*/\s*10", ai_text)
    if match:
        confidence = int(match.group(1))

    return recommendation, confidence


async def analyze_and_track_stock(
    telegram_user_id: int,
    symbol: str,
    indicadores: dict,
) -> str:
    """Generate stock analysis via AI and persist recommendation metadata."""
    prompt = build_stock_analysis_prompt(symbol, indicadores)
    analysis = await call_ai(prompt)
    recommendation, confidence = parse_recommendation_and_confidence(analysis)

    try:
        price = float(indicadores.get("precio_actual", 0) or 0)
        if price > 0:
            await save_ai_recommendation(
                telegram_user_id=telegram_user_id,
                symbol=symbol,
                recommendation=recommendation,
                confidence=confidence,
                price_at_recommendation=price,
            )
    except Exception as exc:
        logger.warning("No se pudo guardar recomendación IA para %s: %s", symbol, exc)

    return analysis


async def analyze_full_and_track_stock(
    telegram_user_id: int,
    symbol: str,
    current_price: float,
    extra_context: str = "",
) -> str:
    prompt = build_full_analysis_prompt(symbol, extra_context=extra_context)
    analysis = await call_ai(prompt)
    recommendation, confidence = parse_recommendation_and_confidence(analysis)
    if current_price > 0:
        try:
            await save_ai_recommendation(
                telegram_user_id=telegram_user_id,
                symbol=symbol,
                recommendation=recommendation,
                confidence=confidence,
                price_at_recommendation=current_price,
            )
        except Exception as exc:
            logger.warning("No se pudo guardar recomendación full analysis: %s", exc)
    return analysis


async def call_ai(prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.2) -> str:
    """Generic AI call wrapper with timeout and friendly exception mapping."""
    if not (_client.api_key):
        raise AIAnalysisError("No API key configurada")

    def _sync_call() -> str:
        completion = _client.chat.completions.create(
            model="sonar-pro",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens or settings.ai_max_tokens,
        )
        return completion.choices[0].message.content or ""

    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _sync_call),
            timeout=settings.ai_analysis_timeout,
        )
        if not result.strip():
            raise AIAnalysisError("Respuesta vacía de IA")
        return result
    except asyncio.TimeoutError as exc:
        raise AIAnalysisError("Timeout IA") from exc
    except AIAnalysisError:
        raise
    except Exception as exc:
        raise AIAnalysisError(str(exc)) from exc


def build_full_analysis_prompt(symbol: str, extra_context: str = "") -> str:
    base = FULL_ANALYSIS.format(symbol=symbol)
    if extra_context:
        return f"{base}\n\nContexto adicional:\n{extra_context}"
    return base


def build_screener_prompt(strategy: str, market: str) -> str:
    return STOCK_SCREENER.format(strategy=strategy, market=market)


def build_earnings_prompt(company: str, report_text: str) -> str:
    return EARNINGS_BREAKDOWN.format(company=company, report_text=report_text)


def build_risk_prompt(symbol: str) -> str:
    return RISK_ANALYSIS.format(symbol=symbol)


def build_compare_prompt(symbol_a: str, symbol_b: str, investor_type: str, timeframe: str) -> str:
    return HEAD_TO_HEAD.format(
        symbol_a=symbol_a,
        symbol_b=symbol_b,
        investor_type=investor_type,
        timeframe=timeframe,
    )


def build_portfolio_builder_prompt(amount: float, strategy: str, timeframe: str, num_stocks: int) -> str:
    return BUILD_PORTFOLIO.format(
        amount=f"{amount:,.2f}",
        strategy=strategy,
        timeframe=timeframe,
        num_stocks=num_stocks,
    )


def build_entry_prompt(symbol: str) -> str:
    return ENTRY_TIMING.format(symbol=symbol)
