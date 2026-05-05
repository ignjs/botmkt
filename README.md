
# BotMKT

![Python](https://img.shields.io/badge/Python-3.11.14-blue)
![Licencia](https://img.shields.io/badge/Licencia-Uso_educativo_y_personal-lightgrey)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-20.7-26A5E4)
![asyncpg](https://img.shields.io/badge/asyncpg-0.29.0-2E8B57)
![yfinance](https://img.shields.io/badge/yfinance-1.2.0-0A7C59)

BotMKT es un bot de Telegram para análisis financiero en español, orientado a inversionistas que buscan disciplina de cartera con apoyo de IA y reglas personalizadas. El bot permite gestionar posiciones, definir perfil de inversión, recibir un plan semanal accionable, crear alertas de precio, calcular métricas cuantitativas y ejecutar órdenes en Alpaca (paper/live con confirmación explícita). Está preparado para ejecución serverless con Webhooks (Flask + Cloud Run). No ejecuta órdenes reales en brokers ni opera cuentas de inversión reales.

---

## Características principales

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

---

## Estructura del proyecto

```text
main.py                         # Entrypoint Flask (webhook), runtime async persistente e integración Telegram
config/                         # Settings y container
db/                             # Acceso DB async + schema bootstrap
handlers/                       # Handlers de Telegram
services/                       # Lógica de negocio y motores cuantitativos
interfaces/telegram/            # Bootstrap bot y error handler
prompts/                        # Prompts markdown base
tests/                          # Pruebas unitarias/integración/e2e
utils/                          # Utilidades (cache, prompt loader, rate limiter)
schema.sql                      # DDL para inicialización manual
requirements.txt                # Dependencias fijadas del proyecto
README.md                       # Documentación principal
```

### Módulos y responsabilidades

| Módulo | Responsabilidad |
|---|---|
| main.py | Expone `/webhook` y `/healthz`, inicializa TelegramBot en modo webhook y procesa updates en runtime async persistente |
| db/ | Conexión asyncpg, validación DATABASE_URL, creación de tablas e índices, CRUD multiusuario |
| handlers/ | Gestión de posiciones, perfil, alertas, mensajes libres, rebalanceo |
| services/ | Métricas de riesgo, optimización, integración IA, reglas, plan semanal, market data |
| prompts/ | Prompts base para análisis IA y reglas |
| utils/ | Cache, prompt loader, rate limiter |
| config/ | Variables de entorno y container |
| tests/ | Pruebas unitarias, integración y e2e |

---

## Requisitos

- Python >= 3.11.14
- PostgreSQL >= 14
- Token de Telegram (BotFather)
- API key de Perplexity (o alternativa OpenAI)
- (Opcional) Cuenta Alpaca paper/live

---

## Instalación y configuración

```bash
git clone https://github.com/ignjs/botmkt.git
cd botmkt
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Crear archivo `.env` con variables mínimas:

```env
TELEGRAM_TOKEN=tu_token
PERPLEXITY_API_KEY=tu_api_key
DATABASE_URL=postgresql://usuario:password@host:5432/botmkt
LOG_LEVEL=INFO
# Opcional:
ALPHA_VANTAGE_KEY=tu_alpha_vantage_key
```

Iniciar bot local (modo webhook):

```bash
python main.py
```

Exponer el endpoint local y registrar webhook en Telegram:

```bash
ngrok http 8080
curl -X POST "https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook" \
   -d "url=https://<tu_subdominio_ngrok>.ngrok-free.app/webhook"
```

Verificar estado del webhook:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_TOKEN>/getWebhookInfo"
```

---

## Variables de entorno

| Variable | Descripción | Requerida | Ejemplo |
|---|---|---|---|
| TELEGRAM_TOKEN | Token del bot de Telegram usado por el runtime webhook | Sí | 123456789:ABCDEF |
| PERPLEXITY_API_KEY | API key para análisis IA | Sí | pplx-abc123 |
| DATABASE_URL | URL PostgreSQL para asyncpg | Sí | postgresql://user:pass@localhost:5432/botmkt |
| LOG_LEVEL | Nivel de logging global | No | INFO |
| ALPHA_VANTAGE_KEY | Clave opcional para fallback de precios | No | AV-xxxxxxxx |
| ATR_MULTIPLIER | Multiplicador ATR para stop-loss dinámico | No | 2.0 |
| ALERT_COOLDOWN_HOURS | Cooldown de alertas repetidas | No | 6 |
| MARKET_OPEN | Apertura mercado (HH:MM) | No | 09:30 |
| MARKET_CLOSE | Cierre mercado (HH:MM) | No | 16:00 |
| MARKET_TZ | Zona horaria del scheduler | No | America/Santiago |
| RISK_FREE_RATE | Tasa libre de riesgo anual (%) | No | 4.5 |
| BENCHMARK_SYMBOL | Benchmark para beta (ej. ^GSPC) | No | ^GSPC |
| AI_ANALYSIS_TIMEOUT | Timeout análisis IA en segundos | No | 60 |
| AI_MAX_TOKENS | Máximo de tokens por análisis IA | No | 2048 |
| EARNINGS_WAIT_TIMEOUT | Timeout para pegar reporte en /earnings | No | 120 |
| ALPACA_API_KEY | Key de Alpaca | No | PK... |
| ALPACA_SECRET_KEY | Secret de Alpaca | No | SK... |
| ALPACA_MODE | paper o live | No | paper |

---

## Comandos del bot y triggers

### Cartera y riesgo

| Comando | Descripción |
|---|---|
| +SYMBOL CANTIDAD PRECIO | Agrega/actualiza posición (con ATR/stop automático) |
| -SYMBOL | Elimina una posición |
| /cartera | Muestra cartera + métricas + stop-loss por posición |
| /metricas | Dashboard cuantitativo (Sharpe, Beta, MDD, HHI) |
| /rebalancear | Optimización Markowitz |

### IA y análisis

| Comando | Descripción |
|---|---|
| /analiza | Analiza cartera completa |
| /analiza SYMBOL | Backtest RSI+MACD + análisis completo Wall Street |
| /screener STRATEGY MERCADO | Screening (growth/valor/dividendos/momentum) |
| /earnings COMPANY | Flujo para analizar reporte de resultados |
| /riesgo SYMBOL | Análisis de downside risk |
| /comparar A B TIPO HORIZONTE | Comparación head-to-head |
| /armar MONTO ESTRATEGIA HORIZONTE ACCIONES | Construcción de portafolio desde cero |
| /entrada SYMBOL | Timing de entrada (comprar/esperar/evitar) |
| /historial_ia | Historial de recomendaciones + hit rate |

### Alertas

| Comando | Descripción |
|---|---|
| /alerta SYMBOL above PRECIO | Crea alerta manual al alza |
| /alerta SYMBOL below PRECIO | Crea alerta manual a la baja |
| /mis_alertas | Lista alertas manuales activas |
| /borrar_alerta ID | Elimina alerta manual |
| /alertas | Historial de alertas proactivas enviadas (24h) |

### Perfil y plan

| Comando | Descripción |
|---|---|
| /perfil | Configura o muestra perfil |
| /perfil_inversion | Alias de /perfil |
| /editar_perfil | Edita perfil guiado |
| /mi_perfil | Muestra perfil actual |
| /plan_semana | Genera plan semanal accionable |
| /cancelar | Cancela flujo conversacional |

### Trading Alpaca

| Comando | Descripción |
|---|---|
| !comprar SYMBOL CANTIDAD | Inicia flujo de compra con confirmación |
| !vender SYMBOL CANTIDAD | Inicia flujo de venta con confirmación |
| CONFIRMAR | Ejecuta orden pendiente (expira en 60s) |
| /cuenta | Resumen de cuenta y posiciones Alpaca |

#### Triggers de lenguaje natural

Entradas detectadas en handlers/message.py y handlers específicos:

| Trigger detectado | Resultado |
|---|---|
| analiza mi cartera | Ejecuta flujo /analiza de cartera |
| plan semanal | Ejecuta flujo /plan_semana |
| que deberia hacer esta semana | Ejecuta flujo /plan_semana |
| IAM / IPSA / dólar / dolar / USD | Mapea a símbolo y entrega análisis |
| configurar perfil | Inicia flujo de perfil |
| editar perfil | Inicia edición de perfil |

---

## Perfil del inversor: 8 campos y validaciones

El cuestionario vive en handlers/investment_profile.py y persiste en investment_profiles.

| Campo | Pregunta | Valores aceptados | Valor por defecto |
|---|---|---|---|
| risk_tolerance | 1/8 Riesgo tolerado (1-10) | Entero entre 1 y 10 | 5 |
| investment_horizon | 2/8 Horizonte | corto, mediano, largo | largo |
| max_position_pct | 3/8 Máximo por posición (%) | 0 < x <= 100 | 25 |
| max_country_pct | 4/8 Máximo por país (%) | 0 < x <= 100 | 70 |
| max_sector_pct | 5/8 Máximo por sector (%) | 0 < x <= 100 | 50 |
| max_drawdown_pct | 6/8 Drawdown máximo (%) | 0 < x <= 100 | 12 |
| preferred_strategy | 7/8 Estrategia | growth, dividendos, valor, mixta | mixta |
| cash_buffer_pct | 8/8 Caja objetivo (%) | 0 < x <= 100 | 10 |

Respuestas especiales soportadas durante edición: mantener, igual, skip, omitir (conserva valor actual); cancelar, /cancelar, no (aborta flujo); actualizar, editar, si, sí (confirma actualización cuando ya existe perfil).

---

## Base de datos

El esquema se crea automáticamente al inicializar el contenedor (Container.build) o manualmente con schema.sql.

| Tabla | Columnas principales | Descripción |
|---|---|---|
| users | id, telegram_user_id, created_at | Identidad única por usuario de Telegram |
| positions | user_id, symbol, quantity, avg_buy_price, created_at, updated_at | Posiciones por usuario con upsert lógico por (user_id, symbol) |
| investment_profiles | user_id, risk_tolerance, investment_horizon, ... | Perfil de inversión usado por reglas y plan semanal |
| risk_snapshots | user_id, fecha, métricas | Persistencia diaria de métricas VaR/Sharpe/Max Drawdown/HHI |
| price_alerts | id, user_id, symbol, price, triggered | Alertas de precio con estado triggered |
| weekly_plans | user_id, fecha, plan | Memoria semanal de planes generados |
| ai_recommendations | id, user_id, symbol, fecha, resultado | Registro de recomendaciones IA |

---

## Tests

```bash
# Suite completa
PYTHONPATH=. pytest -q

# Tests por entregables
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

---

## Troubleshooting y notas de operación

- **DATABASE_URL no configurada**: ValueError al iniciar. Definir en .env y reiniciar.
- **El bot no responde**: Revisar TELEGRAM_TOKEN, webhook activo (`getWebhookInfo`), proceso activo y conectividad.
- **RuntimeError: Event loop is closed**: Verificar que se está usando la versión actual con runtime async persistente en `main.py` (no cerrar loop por request).
- **yfinance no retorna datos**: Verificar símbolo, sufijo de mercado y fallback ALPHA_VANTAGE_KEY.
- **El esquema no se crea**: Revisar permisos, ejecutar schema.sql manualmente si es necesario.
- **scipy.optimize no disponible**: Activar entorno y reinstalar dependencias.

Scheduler proactivo: cada 15 minutos en días hábiles dentro de ventana de mercado (`MARKET_OPEN`/`MARKET_CLOSE`/`MARKET_TZ`). El scheduler diario también actualiza resultados de recomendaciones IA pendientes. En modo `live` de Alpaca, el bot muestra advertencia adicional antes de confirmar.

---

## Despliegue

### Google Cloud Run (recomendado)
1. Construir imagen y desplegar el servicio en Cloud Run exponiendo puerto `8080`.
2. Configurar variables de entorno: `TELEGRAM_TOKEN`, `PERPLEXITY_API_KEY`, `DATABASE_URL`, `LOG_LEVEL` y opcionales.
3. Configurar el webhook apuntando a `https://<servicio>.a.run.app/webhook`.
4. Verificar salud en `/healthz` y revisar logs de inicialización y procesamiento de updates.

Ejemplo de registro de webhook post-deploy:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook" \
   -d "url=https://<tu-servicio>.a.run.app/webhook"
```

### Railway (legacy)
Si usas Railway, mantén HTTPS público y registra el endpoint `/webhook` en Telegram.

### Supabase (solo base de datos)
1. Crear proyecto PostgreSQL en Supabase.
2. Copiar cadena en formato:
   ```text
   postgresql://usuario:password@host:5432/nombre_db
   ```
3. Asignar esa cadena a DATABASE_URL en tu entorno de despliegue.

---

## Flujo mínimo recomendado

```text
1) /perfil
2) +AAPL 10 170
3) +MSFT 5 400
4) /cartera
5) /plan_semana
6) /rebalancear
```

---

## Seguridad, límites y alcance

1. Este proyecto entrega análisis y recomendaciones informativas, no asesoría financiera regulada.
2. No envía órdenes a brokers ni integra ejecución real de trades.
3. Las alertas dependen de disponibilidad de fuentes de mercado.
4. La calidad de planes IA depende de prompts y datos de entrada.
5. Existen límites de rate limit por usuario para evitar abuso de endpoints IA.

---

## Licencia

Desarrollado por Ignjs. Uso educativo y personal. Puedes modificar y adaptar el código según tus necesidades.
