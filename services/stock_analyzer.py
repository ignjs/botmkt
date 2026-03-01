import yfinance as yf
import pandas as pd
import numpy as np
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

async def get_stock_data(symbol: str, retries: int = 3) -> Dict:
    """Versión robusta con retry + minimal calls."""
    
    # Solo histórico básico (evita quoteSummary que dispara 429)
    for attempt in range(retries):
            try:
                ticker = yf.Ticker(symbol)
                
                # MINIMAL: solo history (1 llamada)
                hist = ticker.history(period="1mo", auto_adjust=True, prepost=False)
                if hist.empty or len(hist) < 14:
                    raise ValueError(f"No data para {symbol} (delisted/vacío)")
                close = hist['Close']
                # RSI manual
                delta = close.diff()
                up = delta.clip(lower=0)
                down = -1 * delta.clip(upper=0)
                roll_up = up.rolling(14).mean()
                roll_down = down.rolling(14).mean()
                rs = roll_up / roll_down
                rsi = 100 - (100 / (1 + rs))
                rsi_val = round(float(rsi.iloc[-1]), 2)

                # MACD manual
                exp12 = close.ewm(span=12, adjust=False).mean()
                exp26 = close.ewm(span=26, adjust=False).mean()
                macd_line = exp12 - exp26
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                macd_val = round(float(macd_line.iloc[-1]), 4)

                precio_actual = round(float(close.iloc[-1]), 2)
                compra = precio_actual
                venta = round(compra * 1.004, 2)  # Spread 0.4% simulado
                spread = round(venta - compra, 2)
                indicadores = {
                    'precio_actual': precio_actual,
                    'compra': compra,
                    'venta': venta,
                    'spread': spread,
                    'cambio_24h': round(((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100, 2),
                    'cambio_7d': round(((close.iloc[-1] - close.iloc[-7]) / close.iloc[-7]) * 100, 2) if len(close) >= 8 else 0,
                    'rsi': rsi_val,
                    'macd': macd_val,
                    'volumen': int(hist['Volume'].iloc[-1]),
                    'symbol': symbol
                }
                logger.info(f"✅ {symbol}: OK ({precio_actual})")
                return indicadores
            except Exception as e:
                logger.warning(f"⚠️ {symbol} intento {attempt+1}: {str(e)[:100]}")
                if "429" in str(e) or "Too Many Requests" in str(e):
                    wait = (2 ** attempt) + np.random.uniform(0, 1)
                    logger.info(f"⏳ Rate limit detectado. Esperando {wait:.1f}s")
                    time.sleep(wait)
                    continue
                if attempt == retries - 1:
                    raise ValueError(f"Falló {symbol} tras {retries} intentos: {str(e)}")
    raise ValueError("No data")
    

# Fallback multi-source (simulado)
async def get_stock_data_fallback(symbol: str) -> Optional[Dict]:
    """Simula fallback a otra fuente (Alpha/Static). Devuelve datos estáticos si todo falla."""
    # Aquí podrías integrar Alpha Vantage, Finnhub, etc. Por ahora, datos estáticos demo:
    static_data = {
        'precio_actual': 12500,
        'compra': 12500,
        'venta': 12550,
        'spread': 50,
        'cambio_24h': 0.5,
        'cambio_7d': 2.1,
        'rsi': 48.2,
        'macd': 0.0123,
        'volumen': 1200000,
        'symbol': symbol
    }
    logger.info(f"ℹ️ Fallback estático para {symbol}")
    return static_data
