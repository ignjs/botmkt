# BotMKT: Bot Financiero y API de Análisis de Acciones

## Descripción General
BotMKT es una solución integral que combina un bot de Telegram y una API REST para el análisis financiero de acciones. Permite a los usuarios consultar información técnica y obtener análisis generados por IA (OpenAI/Perplexity) sobre acciones bursátiles, todo en español y con comandos simples.

---

## Características Principales
- **Bot de Telegram**: Consulta de acciones y análisis financiero simplemente enviando el símbolo (ej: `IAM.SN`, `IPSA`, `dólar`).
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
   handlers/message.py   # Handler conversacional (mensaje=análisis)
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
   PERPLEXITY_API_KEY=tu_api_key_perplexity
   BRAIN_API_KEY=tu_api_key_braindata
   ALPHA_KEY=tu_api_key_alpha
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

**UX Conversacional:**
- Envía un mensaje con el símbolo o keyword (ej: `IAM.SN`, `IPSA`, `dólar`)
- El bot responde con análisis financiero, tabla markdown y decisión IA

**Ejemplo:**
```
Usuario: IAM.SN
Bot:
📈 **IAM.SN** (BrainData 20:09)
| Compra 🟢 | Venta 🔴 | Spread ➖ | Vol 💸 |
| $12,500 | $12,550 | $50 | 1,200,000 |
| RSI | MACD |
| 48.2 | 0.0123 |
**IA:** Mantener. Riesgo 4/10. Stop-loss $12,200
```

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
