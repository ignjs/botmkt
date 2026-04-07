# BotMKT: Bot Financiero y API de Análisis de Acciones

## Descripción general
BotMKT es una solución que combina un bot de Telegram y una API REST para análisis financiero de acciones. Permite consultar información técnica, obtener análisis generados por IA y operar como un **asistente privado de disciplina y ejecución de cartera**, con reglas personalizadas y un plan semanal accionable.

---

## Características principales
- **Bot de Telegram** para análisis de acciones, gestión de cartera y consultas en lenguaje natural.
- **Perfil del inversor** con tolerancia al riesgo, horizonte, límites de concentración y caja objetivo.
- **Plan semanal de ejecución** con acciones priorizadas a partir del perfil y la cartera.
- **API REST con FastAPI** para health check y análisis programático.
- **Indicadores técnicos** como RSI, MACD, variaciones porcentuales, volumen y volatilidad.
- **Análisis con IA** para contexto, decisión y resumen ejecutivo en español.
- **Configuración segura** mediante variables de entorno.
- **Arquitectura modular** separada en `handlers`, `services`, `db` y `api`.

## Comandos principales
- `+AAPL 10 170` → agrega o actualiza una posición.
- `-AAPL` → elimina una posición de la cartera.
- `/cartera` → muestra el snapshot actual de la cartera.
- `/analiza` → genera un análisis IA del portafolio o de un símbolo.
- `/perfil` → si ya existe perfil, lo muestra y ofrece actualizarlo; si no existe, inicia el cuestionario.
- `/editar_perfil` → inicia directamente la actualización guiada del perfil.
- `/mi_perfil` → muestra el perfil guardado.
- `/plan_semana` → genera el plan semanal de ejecución.
- `plan semanal` / `que deberia hacer esta semana` → activan el plan en lenguaje natural.

## Ejemplo de uso
```text
👤 +IAM.SN 50 12500
🤖 ✅ IAM.SN agregado (50 @ 12,500)

👤 /perfil
🤖 🧭 Tu perfil de inversión
   - Riesgo tolerado: 5/10
   - Horizonte: largo
   - Máx. por posición: 25%
   ...
   Ya existe un perfil asociado a tu usuario.
   Responde `actualizar` para modificarlo o `cancelar` para dejarlo igual.

👤 actualizar
🤖 Vamos a actualizar tu perfil actual.
   1/8 Riesgo tolerado (1-10). Valor actual: 5

👤 mantener
🤖 2/8 Horizonte de inversión: corto, mediano o largo. Valor actual: largo

👤 /cartera
🤖 📊 **Tu cartera** (Valor: $750k)
| Símbolo | Cant | Precio | Valor | P/L |
| IAM.SN  |  50  | 12,550 | 627k  | +0.4% |
| AAPL    |  10  | 210    | 2.1k  | +4.5% |

👤 /plan_semana
🤖 🗂️ **Plan semanal de ejecución**
1. Estado general: cartera operable, pero concentrada en Chile.
2. Desalineaciones clave: IAM.SN supera tu límite por posición.
3. Acciones: no agregar a IAM.SN, subir caja al 10%, diversificar fuera del mismo mercado.
4. Riesgo actual: Medio (6/10).
5. Urgencia: Media.
```

---

## Migración y uso con PostgreSQL

BotMKT usa `PostgreSQL` vía `asyncpg`. La configuración es simple y no requiere migraciones manuales para el caso base.

### Pasos
1. Crea una base de datos PostgreSQL local o en un proveedor como Railway/Supabase.
2. Agrega la variable `DATABASE_URL` en tu archivo `.env`:

   ```env
   DATABASE_URL=postgresql://usuario:password@localhost:5432/tu_db
   ```

3. Inicia el bot normalmente:

   ```bash
   python main.py
   ```

4. Al arrancar, el bot crea automáticamente las tablas necesarias (`users`, `positions`, `investment_profiles`) si no existen.
5. Si luego migras a otro entorno, solo debes cambiar el valor de `DATABASE_URL`.

### Notas útiles
- Si `DATABASE_URL` no está configurada, el bot no podrá persistir cartera ni perfil.
- El esquema actual está preparado para multiusuario usando `telegram_user_id`.
- No necesitas ejecutar `schema.sql` manualmente en el flujo normal.

---

## Instalación
1. **Clona el repositorio y entra al directorio**:
   ```bash
   git clone <repo_url>
   cd botmkt
   ```
2. **Crea y activa un entorno virtual**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Instala las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configura el archivo `.env`** con tus claves y parámetros básicos:
   ```env
   TELEGRAM_TOKEN=tu_token_telegram
   PERPLEXITY_API_KEY=tu_api_key_perplexity
   DATABASE_URL=postgresql://usuario:password@localhost:5432/tu_db
   API_HOST=127.0.0.1
   API_PORT=8000
   LOG_LEVEL=INFO
   ```

---

## Uso

### Bot de Telegram
Ejecuta el bot con:

```bash
python main.py
```

### Flujo conversacional recomendado
- Envía un símbolo o keyword (ej: `IAM.SN`, `IPSA`, `dólar`) para análisis individual.
- Usa `/cartera` para revisar tu snapshot actual.
- Usa `/perfil` para revisar o crear tu perfil de inversión.
- Usa `/editar_perfil` si quieres modificarlo de forma guiada.
- Durante la edición puedes responder `mantener` para conservar el valor actual de un campo.
- Usa `/plan_semana` o `plan semanal` para recibir 3 a 5 acciones concretas priorizadas.

### Ejemplos
```text
Usuario: IAM.SN
Bot:
📈 **IAM.SN** (BrainData 20:09)
| Compra 🟢 | Venta 🔴 | Spread ➖ | Vol 💸 |
| $12,500 | $12,550 | $50 | 1,200,000 |
| RSI | MACD |
| 48.2 | 0.0123 |
**IA:** Mantener. Riesgo 4/10. Stop-loss $12,200
```

```text
Usuario: que deberia hacer esta semana
Bot:
🗂️ **Plan semanal de ejecución**
- No aumentar tu posición dominante esta semana.
- Reserva caja táctica para no entrar forzado.
- Revisa la tesis de la posición con mayor drawdown.
- Riesgo general actual: Medio.
- Urgencia: Media.
```

### API REST
Ejecuta la API con:

```bash
uvicorn api.endpoints:app --reload
```

**Endpoints disponibles:**
- `GET /health` → verifica el estado de la API.
- `POST /analyze` → analiza una acción con body `{ "symbol": "IAM.SN" }`.

---

## Créditos y Licencia
Desarrollado por Ignjs. Uso educativo y personal. Puedes modificar y adaptar el código según tus necesidades.
