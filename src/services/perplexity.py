from openai import OpenAI
from src.config import Config

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
    
    prompt = f"""
Analiza {symbol}: {tabla}
Da: TENDENCIA corto/largo plazo, DECISIÓN (COMPRAR/VENDER/MANTENER), 
riesgo 1-10, stop-loss. Español, Markdown.
"""
    
    completion = client.chat.completions.create(
        model="sonar-pro",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500
    )
    return completion.choices[0].message.content
