"""WSGI-приложение для PythonAnywhere: принимает вебхук Telegram и обрабатывает обновление."""
import asyncio
import logging
import os
import threading

from dotenv import load_dotenv
from flask import Flask, abort, request
from telegram import Update

import bot
import tarot

load_dotenv(tarot.BASE / ".env")
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # иначе токен попадает в логи
log = logging.getLogger("tarot-bot")
application = Flask(__name__)  # PythonAnywhere ищет именно имя `application`
_lock = threading.Lock()  # хранилище — один файл, обновления обрабатываем по одному


async def _handle(data: dict) -> None:
    tg = bot.build_app()
    async with tg:
        await tg.process_update(Update.de_json(data, tg.bot))


@application.post("/webhook")
def webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != os.getenv("WEBHOOK_SECRET"):
        abort(403)
    try:
        with _lock:
            asyncio.run(_handle(request.get_json(force=True)))
    except Exception:  # отвечаем 200 в любом случае, иначе Telegram будет присылать то же обновление снова
        log.exception("ошибка обработки обновления")
    return "ok"


@application.get("/")
def index():
    return "tarot bot"
