FULL_ANALYSIS = """
Actúa como un analista senior de Wall Street. Analiza {symbol} cubriendo:
- Crecimiento de ingresos (últimos 4 trimestres y tendencia)
- Márgenes (bruto, operacional, neto) vs. industria
- Niveles de deuda (D/E ratio, interest coverage, deuda neta/EBITDA)
- Posición competitiva (ventaja diferencial, cuota de mercado, amenazas)
- Valuación (P/E, P/S, EV/EBITDA) vs. peers históricos y sector

Entrega una recomendación clara: COMPRAR / MANTENER / VENDER con reasoning concreto.
Sé directo. Evita lenguaje ambiguo. Máximo 300 palabras. Responde en español.
"""

STOCK_SCREENER = """
Crea una lista de criterios de screening para encontrar acciones de tipo {strategy}
en el sector/mercado: {market}.

Incluye los métricas financieras exactas, ratios y umbrales específicos para filtrar
oportunidades de alta calidad. Organiza los criterios en: obligatorios (hard filters)
y deseables (soft filters).

Proporciona también 3 ejemplos de acciones actuales que cumplirían estos criterios.
Responde en español con formato de tabla donde sea posible.
"""

EARNINGS_BREAKDOWN = """
Analiza este reporte de resultados de {company} en lenguaje claro:

{report_text}

Estructura tu respuesta así:
1. ¿Qué superó o no alcanzó las expectativas? (con números específicos)
2. ¿Qué señaló el management sobre el futuro? (guidance, tono, riesgos mencionados)
3. ¿Cambia este reporte la tesis de inversión? ¿Por qué sí o no?
4. Veredicto en una línea.

Máximo 250 palabras. Responde en español.
"""

RISK_ANALYSIS = """
Analiza el riesgo bajista de invertir en {symbol}. Cubre obligatoriamente:
- Amenazas estructurales de la industria (disrupción, regulación, ciclo)
- Riesgos competitivos (pérdida de mercado, nuevos entrantes, pricing power)
- Vulnerabilidades del balance (liquidez, vencimientos de deuda, covenant risk)
- Exposición macroeconómica (tasas de interés, FX, ciclo económico, geopolítica)
- Peor escenario realista para esta posición en un horizonte de 12 meses

Cierra con un rating de riesgo del 1 al 10 y el nivel de stop-loss sugerido.
Responde en español con bullet points concisos. Máximo 250 palabras.
"""

HEAD_TO_HEAD = """
Compara {symbol_a} vs {symbol_b} para un inversor de tipo {investor_type}
con horizonte de {timeframe}.

Analiza lado a lado:
- Valuación actual y relativa (¿cuál está más barato?)
- Trayectoria de crecimiento (próximos 2-3 años)
- Salud financiera (balance, flujo de caja, dividendos si aplica)
- Ventaja competitiva (moat, barreras de entrada)

Concluye con una recomendación explícita: ¿cuál es la compra más sólida y por qué?
No des una respuesta ambigua del tipo "depende de cada inversor".
Responde en español. Máximo 300 palabras.
"""

BUILD_PORTFOLIO = """
Tengo ${amount} para invertir en acciones individuales con una estrategia {strategy}
y horizonte de {timeframe}. Construye un portafolio diversificado de {num_stocks} acciones.

Para cada posición incluye:
- Símbolo y nombre de la empresa
- Porcentaje de asignación sugerido
- Tesis de inversión en 2-3 líneas
- Nivel de riesgo de la posición (bajo/medio/alto)

Al final, muestra el balance sectorial y geográfico del portafolio propuesto.
Responde en español con formato de tabla. Sé específico con los tickers.
"""

ENTRY_TIMING = """
Quiero comprar {symbol} pero busco el mejor precio de entrada posible.

Analiza:
- Valuación actual vs. histórica (¿está caro, justo o barato ahora?)
- Acción del precio reciente (momentum, tendencia, niveles clave)
- Soportes y resistencias técnicas relevantes
- Catalizadores próximos que podrían mover el precio (earnings, eventos macro)

Concluye con una de estas 3 opciones y el precio objetivo:
A) Comprar ahora - justificación
B) Esperar pullback a $X - nivel específico
C) Evitar por ahora - razón concreta

Responde en español. Sé directo con los números.
"""
