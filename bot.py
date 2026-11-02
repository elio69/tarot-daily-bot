"""Telegram-бот «Расклад дня». Запуск: python bot.py"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import time

import tarot

log = logging.getLogger("tarot-bot")
SPREAD_BTN = "spread"


def test_spread(seed: int | None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # консоль Windows (cp1251) не печатает эмодзи
    spread = tarot.draw(random.Random(seed))
    print("bright (3 карты)" if len(spread) == 3 else "quiet (1 карта)")
    print(tarot.format_text(spread))


def owner_id() -> int | None:
    return tarot.read_json("state.json", {}).get("chat_id")


def is_owner(update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.id == owner_id()


async def send_spread(bot, chat_id: int) -> None:
    spread = tarot.get_spread(tarot.today())
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


async def cmd_start(update, context) -> None:
    state = tarot.read_json("state.json", {})
    chat = update.effective_chat
    if "chat_id" not in state:
        tarot.write_json("state.json", {"chat_id": chat.id})
    elif state["chat_id"] != chat.id:
        return
    await update.message.reply_text("Привет, Илюша! Каждое утро в 08:00 (МСК) я предложу расклад дня. "
                                    "Сделать его сейчас можно командой /spread.")


async def cmd_spread(update, context) -> None:
    if is_owner(update):
        await send_spread(context.bot, update.effective_chat.id)


async def cmd_history(update, context) -> None:
    if is_owner(update):
        await update.message.reply_text(tarot.format_history())


async def on_button(update, context) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:  # при запуске по расписанию кнопка может быть «просрочена» — расклад всё равно отправляем
        log.warning("callback answer failed", exc_info=True)
    if is_owner(update):
        await send_spread(context.bot, update.effective_chat.id)


async def send_prompt(bot) -> None:
    chat_id = owner_id()
    if chat_id is None:
        return
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Сделать расклад", callback_data=SPREAD_BTN)]])
    await bot.send_message(chat_id, "Илюша, сделать расклад дня?", reply_markup=kb)


async def daily_prompt(context) -> None:
    await send_prompt(context.bot)


def build_app():
    from dotenv import load_dotenv
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler

    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        sys.exit("Не задан BOT_TOKEN (см. .env.example)")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CallbackQueryHandler(on_button, pattern=f"^{SPREAD_BTN}$"))
    app.add_error_handler(on_error)
    return app


async def _once(app) -> None:
    """Один проход для запуска по расписанию (GitHub Actions): обновления + утреннее приглашение."""
    from datetime import datetime

    async with app:
        state = tarot.read_json("state.json", {})
        updates = await app.bot.get_updates(offset=state.get("offset"), timeout=0)
        for u in updates:
            await app.process_update(u)
        if updates:
            state = tarot.read_json("state.json", {})  # /start мог привязать chat_id
            state["offset"] = updates[-1].update_id + 1
            tarot.write_json("state.json", state)
        now = datetime.now(tarot.TZ)
        state = tarot.read_json("state.json", {})
        if now.time() >= time(8, 0) and state.get("last_prompt") != tarot.today() and "chat_id" in state:
            await send_prompt(app.bot)
            state["last_prompt"] = tarot.today()
            tarot.write_json("state.json", state)


async def on_error(update, context) -> None:
    log.error("Ошибка в обработчике", exc_info=context.error)


def run_bot() -> None:
    app = build_app()
    # задача пересоздаётся при каждом старте; chat_id читается из state.json в момент отправки
    app.job_queue.run_daily(daily_prompt, time(8, 0, tzinfo=tarot.TZ), name="daily")
    app.run_polling()


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # иначе токен попадает в логи
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-spread", action="store_true", help="вытянуть расклад в консоль без Telegram")
    ap.add_argument("--seed", type=int, help="seed для --test-spread")
    ap.add_argument("--once", action="store_true", help="один проход без polling (для cron / GitHub Actions)")
    args = ap.parse_args()
    if args.test_spread:
        test_spread(args.seed)
    elif args.once:
        import asyncio
        asyncio.run(_once(build_app()))
    else:
        run_bot()


if __name__ == "__main__":
    main()
