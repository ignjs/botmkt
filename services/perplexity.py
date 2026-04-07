import json
from typing import Dict

from openai import OpenAI

from config import Config
from utils.prompt_loader import load_prompt

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


def build_portfolio_analysis_prompt(tabla_markdown: str) -> str:
    return load_prompt("portfolio_analysis", portfolio_table=tabla_markdown)


def build_portfolio_rules_prompt(profile: dict, diagnosis: dict) -> str:
    return load_prompt(
        "portfolio_rules",
        profile_json=_render_json(profile),
        diagnosis_json=_render_json(diagnosis),
    )


def build_weekly_plan_prompt(profile: dict, diagnosis: dict) -> str:
    return load_prompt(
        "weekly_execution_plan",
        profile_json=_render_json(profile),
        diagnosis_json=_render_json(diagnosis),
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


async def generate_weekly_plan_text(profile: dict, diagnosis: dict) -> str:
    prompt = build_weekly_plan_prompt(profile, diagnosis)
    config = PROMPT_CONFIG["weekly_execution_plan"]
    return _chat(prompt, **config)


async def generate_telegram_plan_summary(plan_text: str, diagnosis: dict) -> str:
    prompt = build_telegram_brief_prompt(plan_text, diagnosis)
    config = PROMPT_CONFIG["telegram_brief"]
    return _chat(prompt, **config)
