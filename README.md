# BotMKT

![Python](https://img.shields.io/badge/Python-3.11.14-blue)
![Licencia](https://img.shields.io/badge/Licencia-Uso_educativo_y_personal-lightgrey)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-20.7-26A5E4)
![asyncpg](https://img.shields.io/badge/asyncpg-0.29.0-2E8B57)
![yfinance](https://img.shields.io/badge/yfinance-1.2.0-0A7C59)

Bot de Telegram y API REST para análisis financiero en español, orientado a inversionistas que quieren disciplina de cartera con apoyo de IA y reglas personalizadas.

---

## 1. ¿Qué es BotMKT?

BotMKT combina un bot de Telegram y una API REST para analizar acciones y portafolios con indicadores técnicos y texto generado por IA.

El proyecto mantiene un perfil de inversión por usuario, evalúa reglas de concentración/riesgo y sugiere un plan semanal de ejecución.

Puede calcular métricas de riesgo de cartera y una propuesta de rebalanceo tipo Markowitz.

No ejecuta órdenes reales en brokers ni opera cuentas de inversión.

---

## 2. Arquitectura

### 2.1 Estructura del repositorio

```text
botmkt/
├── main.py                         # Entry point del bot de Telegram y scheduler de alertas
├── db.py                           # Pool asyncpg, schema automático y acceso a datos
├── schema.sql                      # DDL equivalente para inicialización manual
├── requirements.txt                # Dependencias fijadas del proyecto
├── .python-version                 # Versión base de Python (3.11.14)
├── api/
│   ├── __init__.py
│   └── endpoints.py                # API REST (FastAPI): /health y /analyze
├── config/
│   ├── __init__.py
│   └── config.py                   # Variables de entorno del runtime
├── handlers/
│   ├── __init__.py
│   ├── alerts.py                   # /alerta, /mis_alertas, /borrar_alerta
│   ├── commands.py                 # Handlers legacy no registrados en main.py
│   ├── investment_profile.py       # Flujo guiado de perfil (8 campos)
│   ├── message.py                  # Detección de símbolo/keyword en lenguaje natural
│   └── portfolio.py                # +SYMBOL, -SYMBOL, /cartera, /analiza, /plan_semana, /rebalancear
├── services/
│   ├── __init__.py
│   ├── alert_checker.py            # Job periódico que dispara alertas de precio
│   ├── market_data.py              # Cascada yfinance -> Alpha Vantage -> cache
│   ├── optimizer.py                # Optimización Markowitz con scipy.optimize
│   ├── perplexity.py               # Cliente IA (Perplexity via SDK OpenAI)
│   ├── planner.py                  # Plan semanal con memoria y reglas
│   ├── portfolio_service.py        # Snapshot de cartera y contexto por posición
│   ├── risk_engine.py              # VaR, Sharpe, Max Drawdown, HHI
│   ├── rules_engine.py             # Diagnóstico de reglas vs perfil
│   └── stock_analyzer.py           # Indicadores técnicos por símbolo
├── prompts/
│   ├── stock_analysis.md
│   ├── portfolio_analysis.md
│   ├── portfolio_rules.md
│   ├── weekly_execution_plan.md
│   └── telegram_brief.md
├── tests/
│   └── ...                         # Pruebas unitarias de utilidades y servicios
└── utils/
    ├── cache.py                    # Cache de precios
    ├── prompt_loader.py            # Carga/render de prompts
    └── rate_limiter.py             # Rate limit por usuario
```

### 2.2 Módulos y responsabilidades

| Módulo | Responsabilidad |
|---|---|
| main.py | Construye Application de Telegram, registra handlers, programa chequeo de alertas cada 300s |
| db.py | Conexión asyncpg, validación DATABASE_URL, creación de tablas e índices, CRUD multiusuario |
| api/endpoints.py | Exponer API REST de salud y análisis con autenticación por X-API-Key |
| handlers/portfolio.py | Gestión de posiciones, consulta cartera, análisis IA, plan semanal, rebalanceo |
| handlers/investment_profile.py | Cuestionario conversacional de 8 pasos para perfil de riesgo |
| handlers/message.py | Parseo de símbolos/keywords y respuesta de análisis single-asset |
| handlers/alerts.py | Creación/listado/eliminación de alertas de precio |
| services/stock_analyzer.py | Cálculo de RSI, MACD, variaciones y volumen desde yfinance |
| services/risk_engine.py | Métricas de riesgo de cartera (VaR 95% 1d, Sharpe, Max Drawdown, HHI) |
| services/optimizer.py | Optimización Markowitz con restricciones de perfil |
| services/rules_engine.py | Diagnóstico de desalineaciones del portafolio respecto al perfil |
| services/planner.py | Generación de plan semanal y persistencia del plan para memoria semanal |
| services/alert_checker.py | Job background que dispara alertas y marca triggered=true |
| services/market_data.py | Obtención de precio con fallback y cache obsoleto |
| services/perplexity.py | Integración IA para análisis de acciones/cartera/planes |

---

## 3. Prerrequisitos

1. Python >= 3.11.14
2. PostgreSQL >= 14
3. Cuenta de Telegram y token de bot generado con @BotFather
4. API key de Perplexity (usada mediante SDK OpenAI con base_url de Perplexity)

Validaciones rápidas recomendadas:

```bash
python --version
psql --version
```

---

## 4. Instalación paso a paso

1. Clonar el repositorio.

```bash
git clone https://github.com/ignjs/botmkt.git
cd botmkt
```

2. Crear entorno virtual.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Confirmar versión de Python activa.

```bash
python --version
```

4. Instalar dependencias.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

5. Crear archivo .env con variables mínimas.

```env
TELEGRAM_TOKEN=123456789:ABCDEF...
PERPLEXITY_API_KEY=pplx-xxxxxxxx
API_KEY=mi_api_key_interna
DATABASE_URL=postgresql://usuario:password@localhost:5432/botmkt
API_HOST=127.0.0.1
API_PORT=8000
LOG_LEVEL=INFO
# Opcional fallback de precio:
ALPHA_VANTAGE_KEY=tu_alpha_vantage_key
```

6. Verificar PostgreSQL.

```bash
psql --version
```

7. Opción A: dejar que el bot cree esquema automáticamente al iniciar.

```bash
python main.py
```

8. Opción B: ejecutar schema.sql manualmente si la BD es nueva.

```bash
psql "$DATABASE_URL" -f schema.sql
```

---

## 5. Variables de entorno

| Variable | Descripción | Requerida | Ejemplo |
|---|---|---|---|
| TELEGRAM_TOKEN | Token del bot de Telegram usado por main.py | Sí | 123456789:ABCDEF |
| PERPLEXITY_API_KEY | API key para generar análisis IA en services/perplexity.py | Sí | pplx-abc123 |
| DATABASE_URL | URL PostgreSQL para asyncpg. db.py valida formato | Sí | postgresql://user:pass@localhost:5432/botmkt |
| API_KEY | Clave requerida por POST /analyze vía header X-API-Key | Sí para API /analyze | botmkt-internal-key |
| API_HOST | Host de despliegue API (configurado, no forzado por endpoints.py) | No | 127.0.0.1 |
| API_PORT | Puerto de despliegue API (configurado, no forzado por endpoints.py) | No | 8000 |
| LOG_LEVEL | Nivel de logging global | No | INFO |
| ALPHA_VANTAGE_KEY | Clave opcional para fallback en services/market_data.py | No | AV-xxxxxxxx |

Notas verificadas en código:

1. Si PERPLEXITY_API_KEY no existe, services/perplexity.py lanza ValueError.
2. Si DATABASE_URL no existe o es inválida, db.py lanza ValueError.
3. Si API_KEY no existe o no coincide, POST /analyze retorna 401.
4. ALPHA_VANTAGE_KEY solo se usa en fallback de precios de market_data.py.

---

## 6. Comandos del bot y triggers de lenguaje natural

### 6.1 Comandos y sintaxis

| Comando / Sintaxis | Descripción | Ejemplo de respuesta del bot |
|---|---|---|
| +SYMBOL CANTIDAD PRECIO | Agrega o actualiza posición. Valida símbolo y que cantidad/precio sean > 0 | ✅ AAPL agregado (10.00 @ 170.00) |
| -SYMBOL | Elimina una posición de cartera | ✅ AAPL eliminado de tu cartera |
| /cartera | Muestra snapshot de cartera y agrega métricas de riesgo si se calculan | 📊 **Tu cartera** ... + sección *Métricas de Riesgo* |
| /analiza | Analiza cartera completa con IA | 🎯 **Análisis IA cartera**: ... |
| /analiza SYMBOL | Analiza un símbolo puntual con IA. Si no está en cartera, avisa contexto parcial | ℹ️ No tienes TSLA guardado... luego análisis IA |
| /plan_semana | Genera plan semanal de ejecución según perfil + reglas + IA | Plan con estado, desalineaciones, acciones, riesgo y urgencia |
| /perfil | Muestra perfil existente y solicita confirmación para actualizar. Si no existe, inicia cuestionario | Ya existe un perfil asociado... responde actualizar o cancelar |
| /editar_perfil | Inicia actualización guiada del cuestionario de 8 pasos | Vamos a actualizar tu perfil actual... |
| /mi_perfil | Muestra perfil guardado y sugiere /editar_perfil | 🧭 Tu perfil de inversión ... |
| /perfil_inversion | Alias textual de /perfil en investment_profile.py | Mismo flujo de /perfil |
| /alerta SYMBOL above PRECIO | Crea alerta de precio al alza | ✅ Alerta #12 creada: AAPL cuando sube de $200.00 |
| /alerta SYMBOL below PRECIO | Crea alerta de precio a la baja | ✅ Alerta #13 creada: AAPL cuando baja de $150.00 |
| /mis_alertas | Lista alertas activas no disparadas | 🔔 *Tus alertas activas:* ... |
| /borrar_alerta ID | Elimina alerta por ID si pertenece al usuario | ✅ Alerta #3 eliminada. |
| /rebalancear | Calcula pesos óptimos Markowitz (requiere al menos 2 posiciones) | ⚖️ *Rebalanceo óptimo (Markowitz)* ... |

### 6.2 Triggers de lenguaje natural y entradas libres

Entradas detectadas en main.py (portfolio_pattern) y handlers/message.py:

| Trigger detectado | Ruta interna | Resultado |
|---|---|---|
| analiza mi cartera | portfolio_handler | Ejecuta flujo /analiza de cartera |
| plan semanal | portfolio_handler | Ejecuta flujo /plan_semana |
| que deberia hacer esta semana | portfolio_handler | Ejecuta flujo /plan_semana |
| qué debería hacer esta semana | portfolio_handler | Ejecuta flujo /plan_semana |
| dame mi plan de cartera | portfolio_handler | Ejecuta flujo /plan_semana |
| IAM / IPSA / dólar / dolar / USD | message_handler | Mapea a símbolo y entrega análisis |
| Símbolo válido directo (ej: AAPL, IAM.SN, ^IPSA, USDCLP=X) | message_handler | Consulta mercado + análisis IA |
| configurar perfil | investment_profile_handler | Inicia flujo de perfil |
| editar perfil | investment_profile_handler | Inicia edición de perfil |

### 6.3 Comandos definidos pero no registrados

En handlers/commands.py existen start() y stock_cmd(), pero main.py no registra CommandHandler("start") ni CommandHandler("stock").

Eso implica que /start y /stock no están operativos actualmente salvo que se registren explícitamente.

---

## 7. Perfil del inversor: 8 campos y validaciones

El cuestionario vive en handlers/investment_profile.py y persiste en investment_profiles (db.py + schema.sql).

| Campo | Pregunta | Valores aceptados | Valor por defecto |
|---|---|---|---|
| risk_tolerance | 1/8 Riesgo tolerado (1-10) | Entero entre 1 y 10 | 5 |
| investment_horizon | 2/8 Horizonte | corto, mediano, largo (alias medio -> mediano) | largo |
| max_position_pct | 3/8 Máximo por posición (%) | Número entre 0 y 100. DB exige >0 y <=100 | 25 |
| max_country_pct | 4/8 Máximo por país (%) | Número entre 0 y 100. DB exige >0 y <=100 | 70 |
| max_sector_pct | 5/8 Máximo por sector (%) | Número entre 0 y 100. DB exige >0 y <=100 | 50 |
| max_drawdown_pct | 6/8 Drawdown máximo (%) | Número entre 0 y 100 | 12 |
| preferred_strategy | 7/8 Estrategia | growth, dividendos, valor, mixta | mixta |
| cash_buffer_pct | 8/8 Caja objetivo (%) | Número entre 0 y 100 | 10 |

Respuestas especiales soportadas durante edición:

1. mantener, igual, skip, omitir: conserva valor actual del campo.
2. cancelar, /cancelar, no: aborta flujo.
3. actualizar, editar, si, sí: confirma actualización cuando ya existe perfil.

---

## 8. API REST

### 8.1 Levantar API local

```bash
uvicorn api.endpoints:app --reload
```

### 8.2 GET /health

Auth: ninguna

Response real:

```json
{
  "status": "ok"
}
```

### 8.3 POST /analyze

Auth: obligatoria por header X-API-Key.

Si API_KEY no está configurada o no coincide con header, responde 401.

Body (schema real StockRequest):

```json
{
  "symbol": "IAM.SN"
}
```

Response (estructura real):

```json
{
  "symbol": "IAM.SN",
  "data": {
    "precio_actual": 12500.0,
    "compra": 12500.0,
    "venta": 12550.0,
    "spread": 50.0,
    "cambio_24h": 0.5,
    "cambio_7d": 2.1,
    "rsi": 48.2,
    "macd": 0.0123,
    "volumen": 1200000,
    "symbol": "IAM.SN"
  },
  "analisis": "Texto generado por IA"
}
```

Ejemplo curl completo:

```bash
curl -X POST "http://127.0.0.1:8000/analyze" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mi_api_key_interna" \
  -d '{"symbol":"AAPL"}'
```

Errores esperables:

1. 401 si falta o no coincide X-API-Key.
2. 400 si falla la obtención de datos o el análisis IA.

---

## 9. Base de datos

El esquema se crea automáticamente al iniciar el bot (init_pool en post_init de main.py).

### 9.1 Tablas base solicitadas

| Tabla | Columnas principales | Descripción |
|---|---|---|
| users | id, telegram_user_id, created_at | Identidad única por usuario de Telegram |
| positions | user_id, symbol, quantity, avg_buy_price, created_at, updated_at | Posiciones por usuario con upsert lógico por (user_id, symbol) |
| investment_profiles | user_id, risk_tolerance, investment_horizon, max_position_pct, max_country_pct, max_sector_pct, max_drawdown_pct, preferred_strategy, cash_buffer_pct | Perfil de inversión usado por reglas y plan semanal |

### 9.2 Tablas adicionales activas en código

| Tabla | Uso |
|---|---|
| risk_snapshots | Persistencia diaria de métricas VaR/Sharpe/Max Drawdown/HHI |
| price_alerts | Alertas de precio con estado triggered |
| weekly_plans | Memoria semanal de planes generados |

### 9.3 Inicialización manual de esquema

```sql
-- Opción directa en SQL client
\i schema.sql
```

O por CLI:

```bash
psql "$DATABASE_URL" -f schema.sql
```

---

## 10. Ejecución

### 10.1 Ejecutar bot de Telegram

```bash
python main.py
```

Comportamiento verificado:

1. Inicializa pool asyncpg en post_init.
2. Registra handlers de perfil, cartera, mensajes libres, alertas y rebalanceo.
3. Inicia JobQueue para revisar alertas cada 300 segundos.

### 10.2 Ejecutar solo API

```bash
uvicorn api.endpoints:app --host 127.0.0.1 --port 8000
```

### 10.3 Flujo mínimo recomendado

```text
1) /perfil
2) +AAPL 10 170
3) +MSFT 5 400
4) /cartera
5) /plan_semana
6) /rebalancear
```

---

## 11. Despliegue en producción

### 11.1 Opción Railway (app bot)

1. Crear nuevo proyecto en Railway conectado al repositorio.
2. Configurar variables de entorno: TELEGRAM_TOKEN, PERPLEXITY_API_KEY, DATABASE_URL, API_KEY, LOG_LEVEL.
3. Configurar comando de inicio:

```bash
python main.py
```

4. Validar en logs que aparezca mensaje de inicio de polling y que no falle init_pool.

### 11.2 Opción Supabase (solo base de datos)

1. Crear proyecto PostgreSQL en Supabase.
2. Copiar cadena en formato:

```text
postgresql://usuario:password@host:5432/nombre_db
```

3. Asignar esa cadena a DATABASE_URL en tu entorno de despliegue.

### 11.3 Ejecutar solo API en producción

```bash
uvicorn api.endpoints:app --host 0.0.0.0 --port 8000
```

---

## 12. Troubleshooting

### 12.1 DATABASE_URL no configurada

Síntoma:

```text
ValueError: DATABASE_URL no está configurada. Define la variable en tu entorno o en .env
```

Solución:

1. Definir DATABASE_URL en .env.
2. Verificar formato postgresql://usuario:password@host:5432/db.
3. Reiniciar proceso.

### 12.2 El bot no responde

Síntoma:

1. No hay respuesta en Telegram tras enviar comandos.

Checklist:

1. Confirmar TELEGRAM_TOKEN válido en .env.
2. Revisar que el proceso siga en polling (python main.py sin errores).
3. Confirmar conectividad de red saliente.

### 12.3 yfinance no retorna datos

Síntoma:

```text
El símbolo no existe o no está cotizando...
```

Solución:

1. Verificar símbolo y sufijo de mercado (ejemplo chileno: IAM.SN).
2. Probar índices o FX con formato soportado (^IPSA, USDCLP=X).
3. Configurar ALPHA_VANTAGE_KEY para fallback adicional de precio.

### 12.4 El esquema no se crea

Síntoma:

1. Errores SQL al iniciar o tablas inexistentes.

Solución:

1. Revisar permisos del usuario PostgreSQL sobre CREATE TABLE/INDEX.
2. Ejecutar manualmente schema.sql para diagnosticar el statement que falla.
3. Verificar que DATABASE_URL apunte a la base correcta.

### 12.5 API responde 401 en /analyze

Síntoma:

```json
{"detail":"Clave de API inválida o no autorizada."}
```

Solución:

1. Confirmar que API_KEY está definida en .env.
2. Enviar header exacto X-API-Key con el mismo valor.
3. Verificar que el proceso de API cargó variables de entorno al iniciar.

### 12.6 No se ha podido resolver la importación scipy.optimize

Síntoma:

1. VS Code marca error en from scipy.optimize import minimize.

Solución:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -c "from scipy.optimize import minimize; import scipy; print(scipy.__version__)"
```

Si persiste en el editor:

1. Python: Select Interpreter y elegir .venv.
2. Developer: Reload Window.

---

## 13. Seguridad, límites y alcance

1. Este proyecto entrega análisis y recomendaciones informativas, no asesoría financiera regulada.
2. No envía órdenes a brokers ni integra ejecución real de trades.
3. Las alertas dependen de disponibilidad de fuentes de mercado.
4. La calidad de planes IA depende de prompts y datos de entrada.
5. Existen límites de rate limit por usuario para evitar abuso de endpoints IA.

---

## 14. Créditos y licencia

Desarrollado por Ignjs. Uso educativo y personal. Puedes modificar y adaptar el código según tus necesidades.
