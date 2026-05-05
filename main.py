

import logging
import os
import asyncio
import threading
from flask import Flask, request, jsonify
from config.container import Container
from config.settings import settings

container = None
bot = None
app = Flask(__name__)
_async_loop = None
_async_thread = None
_init_lock = threading.Lock()


def setup_logging():
    logging.basicConfig(level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _start_async_loop() -> None:
    """Run a dedicated asyncio loop for Telegram app lifecycle and webhook processing."""
    global _async_loop
    loop = asyncio.new_event_loop()
    _async_loop = loop
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _ensure_async_runtime() -> None:
    global _async_thread
    if _async_thread and _async_thread.is_alive() and _async_loop and not _async_loop.is_closed():
        return
    _async_thread = threading.Thread(target=_start_async_loop, name="telegram-async-loop", daemon=True)
    _async_thread.start()

    # Wait briefly until loop is ready.
    for _ in range(100):
        if _async_loop and not _async_loop.is_closed():
            return
        threading.Event().wait(0.01)
    raise RuntimeError("No se pudo iniciar el event loop asíncrono")


def _run_on_async_loop(coro):
    if _async_loop is None or _async_loop.is_closed():
        raise RuntimeError("Event loop asíncrono no disponible")
    future = asyncio.run_coroutine_threadsafe(coro, _async_loop)
    return future.result()


@app.route("/webhook", methods=["POST"])
def webhook():
    global container, bot
    from telegram import Update

    try:
        _ensure_async_runtime()
        if bot is None or container is None:
            with _init_lock:
                if bot is None or container is None:
                    logging.warning("Inicializando bot/container en primer request...")
                    try:
                        container = _run_on_async_loop(Container.build())
                        bot = container.telegram_bot()
                        bot.enable_scheduler()
                        _run_on_async_loop(bot.start_webhook_mode())
                        logging.info("Bot y container inicializados correctamente en primer request.")
                    except Exception as e:
                        logging.exception(f"Error inicializando bot/container: {e}")
                        return jsonify({"ok": False, "error": str(e)}), 500

        json_data = request.get_json(force=True)
        logging.info(f"Webhook recibido: {json_data}")
        update = Update.de_json(json_data, bot._app.bot)
        logging.info(f"Procesando update con process_update... Application: {bot._app}, Update: {update}")
        _run_on_async_loop(bot.process_webhook_update(update))
        logging.info("process_update ejecutado correctamente.")
        return jsonify({"ok": True})
    except Exception as e:
        logging.exception("Error procesando webhook: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok"


def main():
    setup_logging()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
