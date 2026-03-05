from openai import OpenAI
from config import Config

client = OpenAI(
    api_key=Config.PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai"
)

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
    
    completion = client.chat.completions.create(
        model="sonar-pro",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500
    )
    return completion.choices[0].message.content


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

    completion = client.chat.completions.create(
        model="sonar-pro",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500
    )
    return completion.choices[0].message.content
