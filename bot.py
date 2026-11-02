"""Telegram-бот «Расклад дня». Запуск: python bot.py (или --once для расписания)"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import datetime, time

import tarot

log = logging.getLogger("tarot-bot")
SPREAD_BTN = "spread"
INTRO_BTN = "intro"
MAX_NAME = 40


def test_spread(seed: int | None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # консоль Windows (cp1251) не печатает эмодзи
    spread = tarot.draw(random.Random(seed))
    print("bright (3 карты)" if len(spread) == 3 else "quiet (1 карта)")
    print(tarot.format_text(spread))


def _user(store: dict, update) -> dict | None:
    return store["users"].get(str(update.effective_chat.id))


async def send_spread(bot, store: dict, chat_id: int) -> None:
    spread = tarot.get_spread(store, str(chat_id), tarot.today())
    tarot.save_store(store)  # сохраняем до отправки: повтор не должен вытянуть другие карты
    if len(spread) == 1:
        with open(tarot.image_path(spread[0]["id"]), "rb") as f:
            await bot.send_photo(chat_id, f.read())
    else:
        from telegram import InputMediaPhoto
        media = []
        for s in spread:
            with open(tarot.image_path(s["id"]), "rb") as f:
                media.append(InputMediaPhoto(f.read(), caption=tarot.caption(s)))
        await bot.send_media_group(chat_id, media)
    await bot.send_message(chat_id, tarot.format_text(spread))


async def ask_name(bot, store: dict, chat_id: int) -> None:
    old = store["users"].get(str(chat_id)) or {}
    store["users"][str(chat_id)] = {
        "name": None, "state": "ask_name", "last_prompt": old.get("last_prompt")}  # смена имени не повторяет приглашение
    tarot.save_store(store)
    await bot.send_message(chat_id, "Привет! Как я могу тебя называть?")


async def welcome(update) -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Познакомиться", callback_data=INTRO_BTN)]])
    await update.message.reply_text(
        "Привет! Я каждое утро присылаю расклад Таро на день. Давай познакомимся.", reply_markup=kb)


async def cmd_start(update, context) -> None:
    store = tarot.load_store()
    user = _user(store, update)
    if user and user["state"] == "ready":
        await update.message.reply_text(
            f"Привет, {user['name']}! Каждое утро в 08:00 (МСК) я предложу расклад дня. "
            "Сделать его сейчас можно командой /spread, сменить имя — /name.")
    else:
        await welcome(update)


async def cmd_name(update, context) -> None:
    await ask_name(context.bot, tarot.load_store(), update.effective_chat.id)


async def on_intro(update, context) -> None:
    await _answer(update.callback_query)
    await ask_name(context.bot, tarot.load_store(), update.effective_chat.id)


async def on_text(update, context) -> None:
    store = tarot.load_store()
    user = _user(store, update)
    if user is None:
        await welcome(update)
        return
    if user["state"] != "ask_name":
        await update.message.reply_text("Я понимаю команды: /spread — расклад дня, /history — последние дни, /name — сменить имя.")
        return
    name = " ".join(update.message.text.split())
    if not name or len(name) > MAX_NAME:
        await update.message.reply_text("Напиши имя покороче, до 40 символов.")
        return
    user.update(name=name, state="ready")
    tarot.save_store(store)
    await update.message.reply_text(
        f"Приятно познакомиться, {name}! Каждое утро в 08:00 (МСК) я буду спрашивать, "
        "не сделать ли расклад дня. Хочешь прямо сейчас — /spread.")


async def _ready_user(update, store: dict) -> dict | None:
    user = _user(store, update)
    if user is None:
        await welcome(update)
    elif user["state"] != "ready":
        await update.message.reply_text("Сначала скажи, как тебя называть — просто напиши имя.")
    else:
        return user
    return None


async def cmd_spread(update, context) -> None:
    store = tarot.load_store()
    if await _ready_user(update, store):
        await send_spread(context.bot, store, update.effective_chat.id)


async def cmd_history(update, context) -> None:
    store = tarot.load_store()
    if await _ready_user(update, store):
        await update.message.reply_text(tarot.format_history(store, str(update.effective_chat.id)))


async def _answer(query) -> None:
    try:
        await query.answer()
    except Exception:  # при запуске по расписанию кнопка может быть «просрочена» — действие всё равно выполняем
        log.warning("callback answer failed", exc_info=True)


async def on_button(update, context) -> None:
    await _answer(update.callback_query)
    store = tarot.load_store()
    user = _user(store, update)
    if user and user["state"] == "ready":
        await send_spread(context.bot, store, update.effective_chat.id)


async def send_due_prompts(bot) -> None:
    """Утреннее приглашение каждому знакомому пользователю, один раз в день, начиная с 08:00 МСК."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if datetime.now(tarot.TZ).time() < time(8, 0):
        return
    store = tarot.load_store()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Сделать расклад", callback_data=SPREAD_BTN)]])
    for uid, user in store["users"].items():
        if user["state"] != "ready" or user.get("last_prompt") == tarot.today():
            continue
        user["last_prompt"] = tarot.today()  # помечаем и при ошибке: заблокировавший бота не должен получать повторы
        try:
            await bot.send_message(int(uid), f"{user['name']}, сделать расклад дня?", reply_markup=kb)
        except Exception:
            log.warning("не удалось отправить приглашение %s", uid, exc_info=True)
    tarot.save_store(store)


async def daily_prompt(context) -> None:
    await send_due_prompts(context.bot)


async def on_error(update, context) -> None:
    log.error("Ошибка в обработчике", exc_info=context.error)


def build_app():
    from dotenv import load_dotenv
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

    load_dotenv(tarot.BASE / ".env")
    token = os.getenv("BOT_TOKEN")
    if not token:
        sys.exit("Не задан BOT_TOKEN (см. .env.example)")
    builder = Application.builder().token(token)
    proxy = os.getenv("TELEGRAM_PROXY")  # на бесплатном PythonAnywhere исходящие запросы идут через прокси
    if proxy:
        builder = builder.proxy(proxy).get_updates_proxy(proxy)
    app = builder.build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("name", cmd_name))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CallbackQueryHandler(on_button, pattern=f"^{SPREAD_BTN}$"))
    app.add_handler(CallbackQueryHandler(on_intro, pattern=f"^{INTRO_BTN}$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    return app


async def _prompts() -> None:
    """Разовая рассылка утренних приглашений (запускается планировщиком PythonAnywhere)."""
    app = build_app()
    async with app:
        await send_due_prompts(app.bot)


async def _set_webhook(url: str) -> None:
    app = build_app()
    async with app:
        await app.bot.set_webhook(url, secret_token=os.environ["WEBHOOK_SECRET"])
        print("webhook:", (await app.bot.get_webhook_info()).url)


def run_bot() -> None:
    app = build_app()
    # задача пересоздаётся при каждом старте; пользователи читаются из хранилища в момент отправки
    app.job_queue.run_daily(daily_prompt, time(8, 0, tzinfo=tarot.TZ), name="daily")
    app.run_polling()


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # иначе токен попадает в логи
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-spread", action="store_true", help="вытянуть расклад в консоль без Telegram")
    ap.add_argument("--seed", type=int, help="seed для --test-spread")
    ap.add_argument("--prompts", action="store_true", help="разослать утренние приглашения и выйти (для планировщика)")
    ap.add_argument("--set-webhook", metavar="URL", help="зарегистрировать вебхук в Telegram")
    args = ap.parse_args()
    if args.test_spread:
        test_spread(args.seed)
    elif args.prompts or args.set_webhook:
        import asyncio
        asyncio.run(_prompts() if args.prompts else _set_webhook(args.set_webhook))
    else:
        run_bot()


if __name__ == "__main__":
    main()
