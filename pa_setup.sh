#!/bin/bash
# Установка на PythonAnywhere: запускать в Bash-консоли из папки проекта (bash pa_setup.sh)
set -e
cd "$(dirname "$0")"
pip install --user -q -r requirements-pa.txt
read -r -s -p "Вставьте BOT_TOKEN от BotFather (ввод скрыт) и нажмите Enter: " TOKEN; echo
SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
cat > .env <<ENV
BOT_TOKEN=$TOKEN
WEBHOOK_SECRET=$SECRET
TELEGRAM_PROXY=http://proxy.server:3128
ENV
chmod 600 .env
echo "Готово: .env создан. Дальше — настройка Web-вкладки (см. README)."
