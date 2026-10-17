"""Give one more person the listings: they press Start in the bot, then

    python -m watcher.add_user <telegram username>     e.g. juliaaa_ku
    python -m watcher.add_user                          lists who wrote to the bot

Adds their chat id to TELEGRAM_CHAT_ID in .env and sends them a welcome message.
"""
import os
import re
import sys

import requests

from .main import ROOT, load_dotenv

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

WELCOME = ("✅ Вам открыт доступ. Сюда будут приходить новые квартиры в аренду в Лимассоле "
           "с фотовольтаикой (1–2 спальни, от 50 м², до €1 700).")


def main() -> None:
    load_dotenv()
    api = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}"
    current = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

    people = {}  # username (lowercase) -> (chat id, display name)
    for u in requests.get(f"{api}/getUpdates", timeout=30).json().get("result", []):
        m = u.get("message") or {}
        c, f = m.get("chat") or {}, m.get("from") or {}
        if c.get("type") == "private" and not f.get("is_bot"):
            name = " ".join(x for x in (f.get("first_name"), f.get("last_name")) if x)
            people[(f.get("username") or str(c["id"])).lower()] = (str(c["id"]), name)

    if len(sys.argv) < 2:
        for user, (cid, name) in people.items():
            print(f"{user}\t{name}\t{'уже получает' if cid in current else 'можно добавить'}")
        return

    user = sys.argv[1].lstrip("@").lower()
    if user not in people:
        sys.exit(f"{user} не писал боту (или это было больше суток назад). "
                 "Пусть откроет бота, нажмёт Start, и запустите команду снова.")
    cid, name = people[user]
    if cid in current:
        sys.exit(f"{name} уже получает объявления.")

    r = requests.post(f"{api}/sendMessage", json={"chat_id": cid, "text": WELCOME}, timeout=30).json()
    if not r.get("ok"):
        sys.exit(f"Не удалось написать {name}: {r.get('description')}")

    env = ROOT / ".env"
    text = env.read_text(encoding="utf-8-sig")
    text = re.sub(r"^TELEGRAM_CHAT_ID=.*$", "TELEGRAM_CHAT_ID=" + ",".join(current + [cid]),
                  text, flags=re.M)
    env.write_text(text, encoding="utf-8")
    print(f"Добавлен(а): {name} (@{user}). Приветствие отправлено.")


if __name__ == "__main__":
    main()
