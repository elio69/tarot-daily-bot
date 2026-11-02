"""Логика расклада: выбор карт, хранение истории, форматирование сообщений."""
from __future__ import annotations

import json
import os
import random
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).parent
DATA = BASE / "data"
CARDS_DIR = DATA / "cards"
TZ = ZoneInfo("Europe/Moscow")
POSITIONS = ["Энергия дня", "На что обратить внимание", "Что ждёт"]
MEANING_KEYS = ["meaning_day", "meaning_attention", "meaning_ahead"]

Card = dict
Spread = list[dict]  # [{"id": ..., "position": ...}]


def today() -> str:
    return datetime.now(TZ).date().isoformat()


def read_json(name: str, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(name: str, obj) -> None:
    # запись через временный файл, чтобы падение посреди записи не портило данные
    path = DATA / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


@lru_cache(maxsize=1)
def cards() -> dict[str, Card]:
    return {c["id"]: c for c in json.loads((DATA / "cards.json").read_text(encoding="utf-8"))}


def draw(rng: random.Random) -> Spread:
    """Старший аркан первой картой -> светлый день (3 карты), иначе тихий (1 карта)."""
    ids = sorted(cards())
    first = rng.choice(ids)
    if cards()[first]["arcana"] == "minor":
        return [{"id": first, "position": None}]
    rest = rng.sample([i for i in ids if i != first], 2)
    return [{"id": cid, "position": pos} for cid, pos in zip([first, *rest], POSITIONS)]


def get_spread(day: str, rng: random.Random | None = None) -> Spread:
    """Расклад дня: возвращает сохранённый или тянет новый и сохраняет."""
    history = read_json("history.json", {})
    if day not in history:
        history[day] = draw(rng or random.Random())
        write_json("history.json", history)
    return history[day]


def image_path(card_id: str) -> Path:
    return CARDS_DIR / cards()[card_id]["image"]


def _first_sentence(text: str) -> str:
    return text.split(". ")[0].rstrip(".") + "."


def format_text(spread: Spread) -> str:
    cs = [cards()[s["id"]] for s in spread]
    if len(cs) == 1:
        c = cs[0]
        return (f"🌿 Тихий день — {c['name_ru']}\n\n{c['meaning_day']}\n\n"
                "Ничего масштабного карты не обещают: день спокойный, можно идти в своём ритме.")
    lines = ["✨ Светлый день: старший аркан открыл расклад.\n"]
    for s, c, key in zip(spread, cs, MEANING_KEYS):
        lines.append(f"{s['position']} — {c['name_ru']}\n{c[key]}\n")
    summary = (f"Итог дня: тон задаёт «{cs[0]['name_ru']}». {_first_sentence(cs[0]['meaning_day'])} "
               f"Держи в голове главное: {cs[1]['name_ru']} подсказывает, где быть внимательнее, "
               f"а {cs[2]['name_ru']} обещает, что день закончится не зря.")
    return "\n".join(lines) + summary


def caption(spread_item: dict) -> str:
    name = cards()[spread_item["id"]]["name_ru"]
    return f"{spread_item['position']}: {name}" if spread_item["position"] else name


def format_history(days: int = 7) -> str:
    history = read_json("history.json", {})
    keys = sorted(history, reverse=True)[:days]
    if not keys:
        return "История пока пуста."
    return "\n".join(
        f"{k}: " + ", ".join(cards()[s["id"]]["name_ru"] for s in history[k]) for k in keys
    )
