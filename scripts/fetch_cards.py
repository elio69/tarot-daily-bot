"""Скачивает колоду Райдера—Уэйта (PD, 1909) с Wikimedia Commons в data/cards/.

Запуск: python scripts/fetch_cards.py
Если сеть блокирует загрузку, скрипт останавливается без обходных путей.
"""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "cards"
UA = "TarotDailyBot/1.0 (personal hobby bot; contact: ilya1997year@gmail.com)"
DELAY = 2.0
MAX_H = 800

MAJOR = ["Fool", "Magician", "High Priestess", "Empress", "Emperor", "Hierophant", "Lovers", "Chariot",
         "Strength", "Hermit", "Wheel of Fortune", "Justice", "Hanged Man", "Death", "Temperance",
         "Devil", "Tower", "Star", "Moon", "Sun", "Judgement", "World"]
MINOR_PREFIX = {"wands": "Wands", "cups": "Cups", "swords": "Swords", "pentacles": "Pents"}


def commons_title(card: dict) -> str:
    num = int(card["id"].rsplit("_", 1)[1])
    if card["arcana"] == "major":
        return f"RWS Tarot {num:02d} {MAJOR[num]}.jpg"
    return f"{MINOR_PREFIX[card['suit']]}{num:02d}.jpg"


def fetch(title: str) -> bytes:
    # Special:FilePath отдаёт файл (уменьшенный сервером до 800px по ширине достаточно для запаса)
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(title) + "?width=1000"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def save_resized(raw: bytes, path: Path) -> None:
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if img.height > MAX_H:
        img = img.resize((round(img.width * MAX_H / img.height), MAX_H), Image.LANCZOS)
    img.save(path, "JPEG", quality=88)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cards = json.loads((DATA / "cards.json").read_text(encoding="utf-8"))
    for card in cards:
        path = OUT / card["image"]
        if path.exists():
            continue
        title = commons_title(card)
        try:
            save_resized(fetch(title), path)
        except (urllib.error.URLError, OSError) as e:
            sys.exit(f"Загрузка не удалась на {title}: {e}\n"
                     f"Положите картинки вручную в {OUT} с именами из data/cards.json (поле image), "
                     "например major_00.jpg, wands_01.jpg, pentacles_14.jpg.")
        print("ok", card["image"])
        time.sleep(DELAY)


if __name__ == "__main__":
    main()
