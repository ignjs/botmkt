from telegram import Update
from telegram.ext import ContextTypes
import re
from db import add_position, remove_position, get_positions
from services.portfolio_service import build_portfolio_snapshot
from services.perplexity import analyze_portfolio, analyze_stock
from services.stock_analyzer import get_stock_data, get_stock_data_fallback

SYMBOL_PATTERN = re.compile(r'^(\^[A-Z0-9]{2,}|[A-Z0-9]+(?:\.[A-Z]{1,5})?|[A-Z0-9]+=[A-Z])$')

async def portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = update.effective_user.id
    text = msg.text.strip()
    # +AAPL 10 170
    if text.startswith('+'):
        try:
            parts = text[1:].strip().split()
            if len(parts) != 3:
                raise ValueError("Formato inválido")

            symbol, qty, price = parts
            symbol = symbol.upper()
            if not SYMBOL_PATTERN.match(symbol):
                await msg.reply_text("Símbolo inválido. Ejemplos válidos: IAM.SN, ^IPSA, USDCLP=X")
                return

            qty_value = float(qty)
            price_value = float(price)

            await add_position(user_id, symbol, qty_value, price_value)
            await msg.reply_text(f"✅ {symbol} agregado ({qty_value:,.2f} @ {price_value:,.2f})")
        except ValueError:
            await msg.reply_text("Formato inválido. Usa: +AAPL 10 170")
        except Exception:
            await msg.reply_text("No pude guardar la posición en este momento. Intenta nuevamente.")
    # -AAPL
    elif text.startswith('-'):
        try:
            symbol = text[1:].strip().upper()
            if not symbol:
                raise ValueError("Formato inválido")
            if not SYMBOL_PATTERN.match(symbol):
                await msg.reply_text("Símbolo inválido. Ejemplos válidos: IAM.SN, ^IPSA, USDCLP=X")
                return

            await remove_position(user_id, symbol)
            await msg.reply_text(f"✅ {symbol} eliminado de tu cartera")
        except ValueError:
            await msg.reply_text("Formato inválido. Usa: -AAPL")
        except Exception:
            await msg.reply_text("Formato inválido. Usa: -AAPL")
    # /cartera
    elif text == '/cartera':
        snap = await build_portfolio_snapshot(user_id)
        await msg.reply_text(f"📊 **Tu cartera** (Valor: ${snap['valor_total']:,.0f})\n{snap['tabla']}", parse_mode="Markdown")
    # /analiza | /analiza IAM.SN
    elif text.lower().startswith('/analiza'):
        target = text[8:].strip()
        target_lower = target.lower()

        analizar_cartera_completa = target == "" or target_lower in {
            "esto", "cartera", "mi cartera", "cartera completa"
        }

        if analizar_cartera_completa:
            snap = await build_portfolio_snapshot(user_id)
            if not snap['detalle']:
                await msg.reply_text("No tienes posiciones en tu cartera.")
                return

            tabla = snap['tabla']
            ia = await analyze_portfolio(tabla)
            await msg.reply_text(f"🎯 **Análisis IA cartera**:\n{ia}", parse_mode="Markdown")
        else:
            symbol = target.upper()
            if not SYMBOL_PATTERN.match(symbol):
                await msg.reply_text("Símbolo inválido. Ejemplos válidos: IAM.SN, ^IPSA, USDCLP=X")
                return
            try:
                try:
                    data = await get_stock_data(symbol)
                except Exception:
                    data = await get_stock_data_fallback(symbol)

                posiciones = await get_positions(user_id)
                posicion = next((p for p in posiciones if p["symbol"].upper() == symbol), None)

                if posicion:
                    qty = float(posicion["quantity"])
                    avg_buy = float(posicion["avg_buy_price"])
                    precio_actual = float(data.get("precio_actual", avg_buy))
                    invested_value = qty * avg_buy
                    market_value = qty * precio_actual
                    position_pl_abs = market_value - invested_value
                    position_pl_pct = ((precio_actual - avg_buy) / avg_buy * 100) if avg_buy else 0

                    data.update({
                        "position_qty": qty,
                        "avg_buy_price": avg_buy,
                        "invested_value": invested_value,
                        "market_value": market_value,
                        "position_pl_abs": position_pl_abs,
                        "position_pl_pct": position_pl_pct,
                    })
                else:
                    await msg.reply_text(
                        f"ℹ️ No tienes {symbol} guardado en cartera. Haré análisis solo con datos de mercado."
                    )

                ia = await analyze_stock(symbol, data)
                await msg.reply_text(f"🎯 **Análisis IA {symbol}**:\n{ia}", parse_mode="Markdown")
            except Exception as e:
                await msg.reply_text(f"No pude analizar {symbol}: {str(e) if str(e) else 'No cotizando'}")
    else:
        await msg.reply_text("Comando no reconocido. Usa +AAPL 10 170, -AAPL, /cartera, /analiza o /analiza IAM.SN.")
