# Бот «Расклад дня» (Таро Райдера—Уэйта)

Бот по кнопке «Сделать расклад» присылает расклад дня (раз в день, повторное нажатие показывает тот же расклад).
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

## Деплой на PythonAnywhere (бесплатно, без карты)
Бот работает по вебхуку: Telegram сам присылает сообщения на `https://ИМЯ.pythonanywhere.com/webhook`, ответ мгновенный.

1. Зарегистрируйтесь на pythonanywhere.com (аккаунт Beginner, бесплатный).
2. Консоль **Bash**:
```bash
git clone https://github.com/elio69/tarot-daily-bot.git && cd tarot-daily-bot && bash pa_setup.sh
```
Скрипт спросит токен (ввод скрыт) и создаст `.env`.
3. Вкладка **Web** → Add a new web app → **Manual configuration** → Python 3.12 (или новее).
   В «Code → WSGI configuration file» замените всё содержимое на:
```python
import sys
sys.path.insert(0, "/home/ИМЯ/tarot-daily-bot")
from pa_wsgi import application
```
   Нажмите **Reload**.
4. В консоли: `python3 bot.py --set-webhook https://ИМЯ.pythonanywhere.com/webhook`
5. (Необязательно) Утреннюю рассылку «сделать расклад?» можно включить внешним cron: GET раз в день на
   `https://ИМЯ.pythonanywhere.com/prompts/<WEBHOOK_SECRET из .env>` (на бесплатном PythonAnywhere планировщика нет).
6. Раз в месяц на вкладке Web нажимайте **Run until 1 month from today**, иначе бесплатное приложение отключится.

Обновить код: `cd ~/tarot-daily-bot && git pull`, затем Reload на вкладке Web.
Данные пользователей лежат в `data/store.json` на сервере (в git не попадают).
