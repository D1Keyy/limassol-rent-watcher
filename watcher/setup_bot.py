"""Connect the bot for local runs: asks for the token, finds your chat id,
sends a test message and writes both to .env (not committed).

1. Open your bot in Telegram and send it any message (e.g. /start).
2. python -m watcher.setup_bot
"""
import getpass
import os
import sys
import time

import requests

from .main import ROOT, load_dotenv

WAIT_SECONDS = 900

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


def main() -> None:
    # The token can be pasted into .env by hand (TELEGRAM_BOT_TOKEN=...) or typed here.
    load_dotenv()
    token = (os.environ.get("TELEGRAM_BOT_TOKEN")
             or getpass.getpass("Токен бота от BotFather (ввод скрыт): ")).strip()
    api = f"https://api.telegram.org/bot{token}"

    me = requests.get(f"{api}/getMe", timeout=30).json()
    if not me.get("ok"):
        sys.exit(f"Telegram не принял токен: {me.get('description')}")
    bot = me["result"]["username"]

    chats = {}
    deadline = time.time() + WAIT_SECONDS
    print(f"Жду сообщение для @{bot}: откройте https://t.me/{bot} и нажмите Start ...", flush=True)
    while not chats and time.time() < deadline:
        # Long polling: Telegram answers as soon as a message arrives (or after 50 s).
        upd = requests.get(f"{api}/getUpdates", params={"timeout": 50}, timeout=70).json()
        for u in upd.get("result", []):
            msg = u.get("message") or {}
            chat = msg.get("chat") or {}
            if chat.get("type") == "private" and not (msg.get("from") or {}).get("is_bot"):
                chats[chat["id"]] = chat.get("username") or chat.get("first_name") or ""
    if not chats:
        sys.exit(f"За {WAIT_SECONDS // 60} мин сообщений для @{bot} не пришло. Откройте "
                 f"https://t.me/{bot}, нажмите Start и запустите эту команду ещё раз.")
    chat_id, name = list(chats.items())[-1]   # whoever wrote last

    r = requests.post(f"{api}/sendMessage", timeout=30, json={
        "chat_id": chat_id,
        "text": "✅ Бот подключён. Новые квартиры в Лимассоле будут приходить сюда.",
    }).json()
    if not r.get("ok"):
        sys.exit(f"Не удалось отправить тестовое сообщение: {r.get('description')}")

    (ROOT / ".env").write_text(f"TELEGRAM_BOT_TOKEN={token}\nTELEGRAM_CHAT_ID={chat_id}\n",
                               encoding="utf-8")
    print(f"Готово: бот @{bot}, чат {chat_id} ({name}). Проверьте Telegram, "
          f"там должно быть тестовое сообщение. Настройки сохранены в .env")


if __name__ == "__main__":
    main()
