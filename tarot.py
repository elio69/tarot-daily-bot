"""Логика расклада: выбор карт, хранилище пользователей, форматирование сообщений."""
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
STORE_ENC = DATA / "store.enc"    # зашифровано ключом STATE_KEY (так хранится в публичном репозитории)
STORE_PLAIN = DATA / "store.json"  # локальная разработка без ключа, в git не попадает
TZ = ZoneInfo("Europe/Moscow")
POSITIONS = ["Энергия дня", "На что обратить внимание", "Что ждёт"]
MEANING_KEYS = ["meaning_day", "meaning_attention", "meaning_ahead"]

Card = dict
Spread = list[dict]  # [{"id": ..., "position": ...}]
# store = {"offset": int|None, "users": {uid: {"name", "state": "ask_name"|"ready", "last_prompt"}},
#          "history": {uid: {day: Spread}}}; uid — chat_id строкой (ключи JSON)


def today() -> str:
    return datetime.now(TZ).date().isoformat()


def _fernet():
    key = os.getenv("STATE_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet
    key = key.strip()
    return Fernet(key + "=" * (-len(key) % 4))  # допускаем ключ без хвостового «=» (теряется при копировании)


def load_store() -> dict:
    f = _fernet()
    path = STORE_ENC if f else STORE_PLAIN
    if path.exists():
        raw = path.read_bytes()
        return json.loads((f.decrypt(raw) if f else raw).decode("utf-8"))
    return _from_legacy()


def save_store(store: dict) -> None:
    f = _fernet()
    path = STORE_ENC if f else STORE_PLAIN
    raw = json.dumps(store, ensure_ascii=False).encode("utf-8")
    tmp = path.with_suffix(".tmp")  # запись через временный файл, чтобы сбой не портил данные
    tmp.write_bytes(f.encrypt(raw) if f else raw)
    os.replace(tmp, path)


def _from_legacy() -> dict:
    """Первый запуск: переносим единственного прежнего пользователя (state.json/history.json), если они есть."""
    store: dict = {"offset": None, "users": {}, "history": {}}
    try:
        old = json.loads((DATA / "state.json").read_text(encoding="utf-8"))
        uid = str(old["chat_id"])
        store["offset"] = old.get("offset")
        store["users"][uid] = {"name": "Илюша", "state": "ready", "last_prompt": old.get("last_prompt")}
        hist = DATA / "history.json"
        store["history"][uid] = json.loads(hist.read_text(encoding="utf-8")) if hist.exists() else {}
    except FileNotFoundError:
        pass
    return store


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


def get_spread(store: dict, uid: str, day: str, rng: random.Random | None = None) -> Spread:
    """Расклад дня пользователя: возвращает сохранённый или тянет новый (вызывающий сохраняет store)."""
    days = store["history"].setdefault(uid, {})
    if day not in days:
        days[day] = draw(rng or random.Random())
    return days[day]


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


def format_history(store: dict, uid: str, days: int = 7) -> str:
    history = store["history"].get(uid, {})
    keys = sorted(history, reverse=True)[:days]
    if not keys:
        return "История пока пуста."
    return "\n".join(
        f"{k}: " + ", ".join(cards()[s["id"]]["name_ru"] for s in history[k]) for k in keys
    )
