# Бот «Расклад дня» (Таро Райдера—Уэйта)

Каждый день в 08:00 по Москве бот спрашивает «Илюша, сделать расклад дня?» и по кнопке присылает расклад.
Старший аркан первой картой → светлый день (3 карты), младший → тихий день (1 карта). Трактовки статичные, без LLM.

## Токен
1. В Telegram откройте @BotFather → `/newbot` → получите токен.
2. `cp .env.example .env` и впишите токен в `BOT_TOKEN=`, а в `STATE_KEY=` — ключ шифрования (команда в `.env.example`).
   Те же два значения добавьте как секреты репозитория (Settings → Secrets and variables → Actions): `BOT_TOKEN` и `STATE_KEY`.

## Локальный запуск
```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/fetch_cards.py                   # картинки в data/cards/
python bot.py
```
Затем напишите боту `/start`: он спросит, как вас называть, и будет обращаться по имени. Бот открыт для всех — ссылку можно слать друзьям. Команды: `/spread`, `/history`, `/name`.
Данные пользователей лежат в `data/store.enc` (шифруется `STATE_KEY`; без ключа — `data/store.json` локально).

Проверка без Telegram: `python bot.py --test-spread --seed 1`.

## Деплой
**systemd (VPS):** скопируйте проект в `/opt/tarot-bot`, создайте venv, затем
```bash
sudo cp deploy/tarot-bot.service /etc/systemd/system/
sudo systemctl enable --now tarot-bot
```
**Docker:**
```bash
docker build -t tarot-bot .
docker run -d --restart unless-stopped --env-file .env -v tarot-data:/app/data tarot-bot
```
Состояние (`state.json`, `history.json`) лежит в `data/` — это и есть том.
Картинки в образ попадают из `data/cards/` (скачайте их до сборки).
