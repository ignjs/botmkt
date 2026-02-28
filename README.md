# BotMKT: Bot Financiero y API de Análisis de Acciones

## Descripción General
BotMKT es una solución integral que combina un bot de Telegram y una API REST para el análisis financiero de acciones. Permite a los usuarios consultar información técnica y obtener análisis generados por IA (OpenAI/Perplexity) sobre acciones bursátiles, todo en español y con comandos simples.

---

## Características Principales
- **Bot de Telegram**: Consulta de acciones y análisis financiero mediante comandos como `/stock`.
- **API REST (FastAPI)**: Endpoints para análisis de acciones y health check.
- **Indicadores Técnicos**: RSI, MACD, variaciones porcentuales, volumen y volatilidad.
- **Análisis con IA**: Generación de análisis de tendencia, decisión (comprar/vender/mantener), riesgo y sugerencia de stop-loss usando modelos de lenguaje.
- **Configuración Segura**: Uso de variables de entorno para claves y tokens sensibles.
- **Código Modular**: Separación clara entre configuración, handlers, servicios y API.

---

## Estructura del Proyecto
```
bot.py                  # Script principal del bot de Telegram
requirements.txt        # Dependencias del proyecto
api/endpoints.py        # Endpoints de la API REST
src/
  main.py               # Inicialización del bot
  config/config.py      # Configuración y variables de entorno
  handlers/commands.py  # Handlers de comandos del bot
  services/
    perplexity.py       # Servicio de análisis IA
    stock_analyzer.py   # Servicio de indicadores técnicos
```

---

## Instalación
1. **Clona el repositorio y entra al directorio:**
   ```bash
   git clone <repo_url>
   cd botmkt
   ```
2. **Crea y activa un entorno virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configura el archivo `.env` con tus claves:**
   ```env
   TELEGRAM_TOKEN=tu_token_telegram
   OPENAI_API_KEY=tu_api_key_openai
   PERPLEXITY_API_KEY=tu_api_key_perplexity
   API_HOST=127.0.0.1
   API_PORT=8000
   LOG_LEVEL=INFO
   ```

---

## Uso
### Bot de Telegram
Ejecuta el bot:
```bash
python src/main.py
```
Comandos disponibles:
- `/start`: Mensaje de bienvenida
- `/stock <SÍMBOLO>`: Analiza una acción (ejemplo: `/stock IAM.SN`)

### API REST
Ejecuta la API:
```bash
uvicorn api.endpoints:app --reload
```
Endpoints:
- `GET /health`: Verifica el estado de la API
- `POST /analyze`: Analiza una acción (body: `{ "symbol": "IAM.SN" }`)

---

## Créditos y Licencia
Desarrollado por Ignacio. Uso educativo y personal. Puedes modificar y adaptar el código según tus necesidades.
