import json

from openai import OpenAI

from config import Config

client = OpenAI(
    api_key=Config.PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai"
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


async def analyze_stock(symbol: str, indicadores: dict) -> str:
    """Análisis IA con Perplexity."""
    tabla = f"""
| Precio | ${indicadores['precio_actual']}
| Cambio 24h | {indicadores['cambio_24h']}%
| RSI | {indicadores['rsi']}
| MACD | {indicadores['macd']}
"""

    contexto_posicion = ""
    if "position_qty" in indicadores and "avg_buy_price" in indicadores:
        contexto_posicion = f"""

Datos de mi posición en cartera:
| Cantidad | {indicadores['position_qty']}
| Precio compra promedio | ${indicadores['avg_buy_price']}
| Valor invertido | ${indicadores.get('invested_value', 0):,.2f}
| Valor actual | ${indicadores.get('market_value', 0):,.2f}
| P/L posición | ${indicadores.get('position_pl_abs', 0):,.2f} ({indicadores.get('position_pl_pct', 0):+.2f}%)
"""

    prompt = f"""
Analiza {symbol}: {tabla}{contexto_posicion}
Da: TENDENCIA corto/largo plazo, DECISIÓN (COMPRAR/VENDER/MANTENER),
riesgo 1-10, stop-loss. Si hay datos de posición, incorpora recomendación según costo promedio y P/L. Español, Markdown.
"""
    return _chat(prompt, temperature=0.2, max_tokens=500)


async def analyze_portfolio(tabla_markdown: str) -> str:
    """Análisis IA para cartera usando tabla consolidada."""
    prompt = f"""
Analiza la siguiente cartera:

{tabla_markdown}

Entrega en español y breve:
- Exposición por concentración (si hay alta concentración, indicarlo)
- Nivel de riesgo (1-10)
- Señales generales del escenario actual
- Sugerencia concreta (rebalancear/mantener/reducir riesgo)
"""
    return _chat(prompt, temperature=0.2, max_tokens=500)


def build_portfolio_rules_prompt(profile: dict, diagnosis: dict) -> str:
    return f"""
Eres un asistente privado de disciplina de cartera. Tu tarea es evaluar una cartera contra reglas explícitas del usuario.

Perfil del inversor:
{json.dumps(profile, ensure_ascii=False, indent=2, default=str)}

Diagnóstico estructurado de la cartera:
{json.dumps(diagnosis, ensure_ascii=False, indent=2, default=str)}

Instrucciones:
- Responde en español.
- No prometas rentabilidad ni uses lenguaje promocional.
- Señala solo desalineaciones reales presentes en el diagnóstico.
- Distingue claramente entre breach de regla, warning y oportunidad.
- Sé concreto: menciona pesos, límites y el porqué importa.
- Máximo 180 palabras.
""".strip()


def build_weekly_plan_prompt(profile: dict, diagnosis: dict) -> str:
    return f"""
Eres un Quant PM que transforma reglas de cartera en ejecución semanal.

Perfil del inversor:
{json.dumps(profile, ensure_ascii=False, indent=2, default=str)}

Diagnóstico estructurado:
{json.dumps(diagnosis, ensure_ascii=False, indent=2, default=str)}

Genera un "Plan semanal de ejecución" para Telegram con este formato exacto:
1. Estado general de la cartera.
2. Principales desalineaciones con reglas.
3. 3 a 5 acciones concretas para esta semana, priorizadas.
4. Riesgo general actual.
5. Nivel de urgencia.

Reglas de estilo:
- Español claro, tono serio y ejecutivo.
- Máximo 220 palabras.
- Evita vaguedades como "seguir monitoreando" si no agregan acción.
- No inventes datos faltantes.
- No recomiendes operar de más si la cartera está alineada.
- Nunca prometas resultados ni uses asesoría garantizada.
""".strip()


def build_telegram_brief_prompt(plan_text: str, diagnosis: dict) -> str:
    return f"""
Resume el siguiente plan semanal para que quede perfecto en Telegram.

Plan base:
{plan_text}

Contexto:
{json.dumps(diagnosis.get('portfolio_summary', {}), ensure_ascii=False, indent=2, default=str)}

Reglas:
- Mantén el contenido en español.
- Máximo 140 palabras.
- Conserva 3 a 5 acciones concretas.
- Formato final listo para pegar en Telegram con bullets o numeración.
- Sin promesas de rentabilidad.
""".strip()


async def analyze_portfolio_against_rules(profile: dict, diagnosis: dict) -> str:
    return _chat(build_portfolio_rules_prompt(profile, diagnosis), temperature=0.1, max_tokens=450)


async def generate_weekly_plan_text(profile: dict, diagnosis: dict) -> str:
    return _chat(build_weekly_plan_prompt(profile, diagnosis), temperature=0.15, max_tokens=650)


async def generate_telegram_plan_summary(plan_text: str, diagnosis: dict) -> str:
    return _chat(build_telegram_brief_prompt(plan_text, diagnosis), temperature=0.1, max_tokens=300)
