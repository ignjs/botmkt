# BotMKT

BotMKT es un bot de Telegram para análisis financiero en español con foco en disciplina de cartera.

El proyecto permite gestionar posiciones, definir perfil de inversión, recibir un plan semanal accionable, crear alertas de precio y calcular un rebalanceo cuantitativo de tipo Markowitz.

No ejecuta órdenes reales en brokers.

## Características

- Bot de Telegram como única interfaz de usuario.
- Gestión de cartera con comandos de alta/baja de posiciones.
- Vista de cartera enriquecida: valor total, tabla con precios/P&L actualizados y métricas de riesgo.
- Perfil del inversor con 8 campos y validaciones (riesgo, horizonte, límites de concentración, estrategia, caja objetivo).
- Plan semanal de ejecución accionable basado en reglas e IA.
- Alertas de precio con chequeo periódico en background (cada 5 minutos).
- Métricas de riesgo de cartera: VaR 95%, Sharpe anual, Max Drawdown, HHI concentración.
- Rebalanceo cuantitativo de cartera (Markowitz con scipy, multistep con fallback).
- Análisis por símbolo con datos de mercado en tiempo real y sentimiento IA.
- Arquitectura limpia por capas: `domain` / `application` / `infrastructure` / `interfaces`.
- Persistencia multiusuario en PostgreSQL vía asyncpg con pool asíncrono.
- Configuración tipada con pydantic-settings y carga automática de `.env`.

## Estructura del proyecto

```
main.py                    # Entrypoint async con DI container
config/
  settings.py              # Configuración tipada (pydantic-settings)
  container.py             # Composición de dependencias
domain/                    # Entidades, value objects, excepciones
application/               # Puertos y casos de uso
infrastructure/            # Repositorios PostgreSQL y adaptadores externos
interfaces/telegram/       # Bot, handlers y error handler de Telegram
handlers/                  # Handlers legacy (perfil, alertas, portfolio, comandos)
services/                  # Lógica de negocio (optimizer, risk_engine, planner, etc.)
utils/                     # Cache, rate limiter, prompt loader
tests/                     # Tests unitarios, integración y e2e
```

## Requisitos

- Python 3.11 o superior.
- PostgreSQL 14 o superior.
- Token de Telegram generado con BotFather.
- Clave de API de Perplexity para análisis IA.

Validación rápida:

```bash
python --version
psql --version
```

## Instalación

1. Clonar el repositorio.

```bash
git clone https://github.com/ignjs/botmkt.git
cd botmkt
```

2. Crear y activar entorno virtual.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Instalar dependencias.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. Configurar `.env`.

```env
TELEGRAM_TOKEN=tu_token
DATABASE_URL=postgresql://usuario:password@host:5432/botmkt
PERPLEXITY_API_KEY=tu_api_key
LOG_LEVEL=INFO
```

Variables opcionales:

```env
OPENAI_API_KEY=        # Alternativa al cliente de Perplexity
RISK_FREE_RATE=5.0     # Tasa libre de riesgo anual (%) para Sharpe
BENCHMARK_SYMBOL=^GSPC # Benchmark de referencia
ATR_MULTIPLIER=2.0     # Multiplicador ATR para stops
ALERT_COOLDOWN_HOURS=4 # Cooldown entre alertas del mismo símbolo
```

5. Iniciar bot.

```bash
python main.py
```

El esquema de base de datos se crea automáticamente al iniciar.

Si prefieres inicialización manual:

```bash
psql "$DATABASE_URL" -f schema.sql
```

## Variables de entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `TELEGRAM_TOKEN` | Token del bot de Telegram | Sí |
| `DATABASE_URL` | URL PostgreSQL en formato `postgresql://...` | Sí |
| `PERPLEXITY_API_KEY` | API key de Perplexity para análisis IA | Sí |
| `LOG_LEVEL` | Nivel de logs (`DEBUG`, `INFO`, `WARNING`) | No |
| `OPENAI_API_KEY` | Alternativa al cliente Perplexity | No |
| `RISK_FREE_RATE` | Tasa libre de riesgo anual (%) para Sharpe — defecto: `5.0` | No |
| `BENCHMARK_SYMBOL` | Símbolo de benchmark — defecto: `^GSPC` | No |
| `ATR_MULTIPLIER` | Multiplicador para stops dinámicos — defecto: `2.0` | No |
| `ALERT_COOLDOWN_HOURS` | Horas mínimas entre notificaciones del mismo símbolo — defecto: `4` | No |

## Comandos del bot

### Cartera

| Comando / Sintaxis | Descripción |
|---|---|
| `+SYMBOL CANTIDAD PRECIO` | Agrega o actualiza posición |
| `-SYMBOL` | Elimina una posición |
| `/cartera` | Muestra cartera con valor, P&L actual y métricas de riesgo |
| `/analiza` | Analiza cartera completa con IA |
| `/analiza SYMBOL` | Analiza un símbolo específico con IA |
| `/rebalancear` | Calcula pesos óptimos de Markowitz |

### Perfil de inversión

| Comando | Descripción |
|---|---|
| `/perfil` | Inicia configuración de perfil o muestra el existente |
| `/perfil_inversion` | Alias de `/perfil` |
| `/editar_perfil` | Edita perfil en flujo guiado de 8 pasos |
| `/mi_perfil` | Muestra perfil guardado actual |
| `/cancelar` | Cancela flujo en curso |

### Plan semanal

| Comando | Descripción |
|---|---|
| `/plan_semana` | Genera plan semanal accionable basado en perfil y cartera |

### Alertas

| Comando | Descripción |
|---|---|
| `/alerta SYMBOL above PRECIO` | Crea alerta cuando el símbolo sube del precio dado |
| `/alerta SYMBOL below PRECIO` | Crea alerta cuando el símbolo baja del precio dado |
| `/mis_alertas` | Lista alertas activas |
| `/borrar_alerta ID` | Elimina alerta por id |

### Análisis rápido

| Comando | Descripción |
|---|---|
| `/start` | Bienvenida y ayuda inicial |
| `/stock SYMBOL` | Análisis rápido de un símbolo |
| `SYMBOL` (texto libre) | Cotización y análisis IA del símbolo |

### Lenguaje natural

Los siguientes textos activan el plan semanal sin usar `/plan_semana`:

- `plan semanal`
- `que deberia hacer esta semana`
- `qué debería hacer esta semana`
- `dame mi plan de cartera`

Y para analizar cartera:

- `analiza mi cartera`

## Base de datos

Tablas principales:

| Tabla | Descripción |
|---|---|
| `users` | Usuarios registrados |
| `positions` | Posiciones de cartera por usuario |
| `investment_profiles` | Perfil de inversión por usuario |
| `risk_snapshots` | Histórico de métricas de riesgo calculadas |
| `price_alerts` | Alertas de precio activas |
| `weekly_plans` | Planes semanales generados |

## Tests

```bash
# Suite completa
pytest -q

# Solo unitarios
pytest tests/unit -q

# Con cobertura
pytest --cov=. --cov-report=term-missing -q
```

## Troubleshooting

### DATABASE_URL no configurada

```text
ValidationError: DATABASE_URL field required
```

Solución: definir `DATABASE_URL` en `.env` y reiniciar.

### El bot no responde

1. Verifica `TELEGRAM_TOKEN`.
2. Revisa que `python main.py` quede en ejecución sin errores.
3. Confirma conectividad a internet.

### yfinance no devuelve datos

1. Valida el ticker y sufijo de mercado (ejemplo: `IAM.SN`).
2. Prueba índices y FX soportados (`^IPSA`, `USDCLP=X`).

### No se crea el schema

1. Verifica permisos de PostgreSQL para crear tablas e índices.
2. Ejecuta `schema.sql` manualmente para identificar el error puntual:

```bash
psql "$DATABASE_URL" -f schema.sql
```

### Error con scipy.optimize

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -c "from scipy.optimize import minimize; import scipy; print(scipy.__version__)"
```

### Warning `asyncio.CancelledError` al detener el bot

Es normal al detener el proceso con Ctrl+C o desde el debugger. El bot ejecuta un shutdown ordenado y el warning no indica pérdida de datos.

## Licencia y créditos

Desarrollado por Ignjs. Uso educativo y personal. Puedes modificar y adaptar el código según tus necesidades.
