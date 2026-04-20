# BotMKT

BotMKT es un bot de Telegram para análisis financiero en español con foco en disciplina de cartera.

El proyecto permite gestionar posiciones, definir perfil de inversión, recibir un plan semanal accionable, crear alertas de precio, calcular métricas cuantitativas y ejecutar órdenes en Alpaca (paper/live con confirmación explícita).

## Características

- Bot de Telegram como interfaz principal.
- Gestión de cartera con comandos de alta/baja de posiciones.
- Stop-loss dinámico por ATR(14) calculado automáticamente por posición.
- Vista de cartera con valor total, P/L, stop-loss y métricas de riesgo.
- Alertas proactivas programadas (stop-loss, RSI extremo, volumen anormal) con deduplicación por cooldown.
- Perfil del inversor con 8 campos y validaciones.
- Plan semanal accionable basado en reglas + IA.
- Métricas cuantitativas de portafolio: Sharpe, Beta, Max Drawdown y HHI.
- Rebalanceo cuantitativo (Markowitz).
- Registro de recomendaciones IA y evaluación de aciertos a 5/10/20 días hábiles.
- Backtest rápido RSI+MACD (2 años) antes del análisis IA por símbolo.
- 7 comandos avanzados de análisis IA (screener, riesgo, comparar, timing, etc.).
- Integración con Alpaca para órdenes de compra/venta en paper o live.
- Persistencia multiusuario en PostgreSQL vía asyncpg.

## Estructura del proyecto

```text
main.py                    # Entrypoint async
config/                    # Settings y container
db/                        # Acceso DB async + schema bootstrap
handlers/                  # Handlers de Telegram
services/                  # Lógica de negocio y motores cuantitativos
interfaces/telegram/       # Bootstrap bot y error handler
api/                       # API FastAPI (/metrics/{telegram_user_id})
prompts/                   # Prompts markdown base
tests/                     # Tests unitarios/integración/e2e
```

## Requisitos

- Python 3.11 o superior.
- PostgreSQL 14 o superior.
- Token de Telegram (BotFather).
- API key de Perplexity/OpenAI.
- (Opcional E5) Cuenta Alpaca paper/live.

## Instalación

```bash
git clone https://github.com/ignjs/botmkt.git
cd botmkt
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Configurar `.env` mínimo:

```env
TELEGRAM_TOKEN=tu_token
DATABASE_URL=postgresql://usuario:password@host:5432/botmkt
PERPLEXITY_API_KEY=tu_api_key
LOG_LEVEL=INFO
```

Iniciar bot:

```bash
python main.py
```

## Variables de entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `TELEGRAM_TOKEN` | Token del bot de Telegram | Sí |
| `DATABASE_URL` | URL PostgreSQL | Sí |
| `PERPLEXITY_API_KEY` | API key de Perplexity | Sí* |
| `OPENAI_API_KEY` | API key alternativa | Sí* |
| `LOG_LEVEL` | Nivel de logs | No |
| `ATR_MULTIPLIER` | Multiplicador ATR para stop-loss dinámico | No |
| `ALERT_COOLDOWN_HOURS` | Cooldown de alertas repetidas | No |
| `MARKET_OPEN` | Apertura mercado (HH:MM) | No |
| `MARKET_CLOSE` | Cierre mercado (HH:MM) | No |
| `MARKET_TZ` | Zona horaria del scheduler | No |
| `RISK_FREE_RATE` | Tasa libre de riesgo anual (%) | No |
| `BENCHMARK_SYMBOL` | Benchmark para beta (ej. `^GSPC`) | No |
| `AI_ANALYSIS_TIMEOUT` | Timeout análisis IA en segundos | No |
| `AI_MAX_TOKENS` | Máximo de tokens por análisis IA | No |
| `EARNINGS_WAIT_TIMEOUT` | Timeout para pegar reporte en `/earnings` | No |
| `ALPACA_API_KEY` | Key de Alpaca | No |
| `ALPACA_SECRET_KEY` | Secret de Alpaca | No |
| `ALPACA_MODE` | `paper` o `live` | No |

\* Debes configurar al menos una (`PERPLEXITY_API_KEY` u `OPENAI_API_KEY`).

## Comandos del bot

### Cartera y riesgo

| Comando | Descripción |
|---|---|
| `+SYMBOL CANTIDAD PRECIO` | Agrega/actualiza posición (con ATR/stop automático) |
| `-SYMBOL` | Elimina una posición |
| `/cartera` | Muestra cartera + métricas + stop-loss por posición |
| `/metricas` | Dashboard cuantitativo (Sharpe, Beta, MDD, HHI) |
| `/rebalancear` | Optimización Markowitz |

### IA y análisis

| Comando | Descripción |
|---|---|
| `/analiza` | Analiza cartera completa |
| `/analiza SYMBOL` | Backtest RSI+MACD + análisis completo Wall Street |
| `/screener STRATEGY MERCADO` | Criterios de screening (growth/valor/dividendos/momentum) |
| `/earnings COMPANY` | Flujo conversacional para analizar reporte de resultados |
| `/riesgo SYMBOL` | Análisis de downside risk |
| `/comparar A B TIPO HORIZONTE` | Comparación head-to-head |
| `/armar MONTO ESTRATEGIA HORIZONTE ACCIONES` | Construcción de portafolio desde cero |
| `/entrada SYMBOL` | Timing de entrada (comprar/esperar/evitar) |
| `/historial_ia` | Historial de recomendaciones + hit rate |

### Alertas

| Comando | Descripción |
|---|---|
| `/alerta SYMBOL above PRECIO` | Crea alerta manual al alza |
| `/alerta SYMBOL below PRECIO` | Crea alerta manual a la baja |
| `/mis_alertas` | Lista alertas manuales activas |
| `/borrar_alerta ID` | Elimina alerta manual |
| `/alertas` | Historial de alertas proactivas enviadas (24h) |

### Perfil y plan

| Comando | Descripción |
|---|---|
| `/perfil` | Configura o muestra perfil |
| `/perfil_inversion` | Alias de `/perfil` |
| `/editar_perfil` | Edita perfil guiado |
| `/mi_perfil` | Muestra perfil actual |
| `/plan_semana` | Genera plan semanal accionable |
| `/cancelar` | Cancela flujo conversacional |

### Trading Alpaca

| Comando | Descripción |
|---|---|
| `!comprar SYMBOL CANTIDAD` | Inicia flujo de compra con confirmación |
| `!vender SYMBOL CANTIDAD` | Inicia flujo de venta con confirmación |
| `CONFIRMAR` | Ejecuta orden pendiente (expira en 60s) |
| `/cuenta` | Resumen de cuenta y posiciones Alpaca |

## Base de datos

Tablas principales:

- `users`
- `positions` (incluye `stop_loss` y `atr`)
- `investment_profiles`
- `risk_snapshots`
- `price_alerts`
- `alerts_sent`
- `weekly_plans`
- `ai_recommendations`

## Tests

```bash
# Suite completa
PYTHONPATH=. pytest -q

# Tests nuevos por entregables
PYTHONPATH=. pytest -q \
  tests/test_risk_calculator.py \
  tests/test_alert_engine.py \
  tests/test_portfolio_metrics.py \
  tests/test_recommendation_tracker.py \
  tests/test_backtester.py \
  tests/test_analysis_prompts.py \
  tests/test_e7_handlers.py \
  tests/test_broker_service.py
```

## Notas de operación

- Scheduler proactivo: cada 15 minutos en días hábiles dentro de ventana de mercado (`MARKET_OPEN`/`MARKET_CLOSE`/`MARKET_TZ`).
- El scheduler diario también actualiza resultados de recomendaciones IA pendientes.
- En modo `live` de Alpaca, el bot muestra advertencia adicional antes de confirmar.

## Licencia

Desarrollado por Ignjs. Uso educativo y personal.
