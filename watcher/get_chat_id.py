"""Print the chat id of whoever last wrote to the bot.

1. Open your bot in Telegram and send it any message (e.g. /start).
2. python -m watcher.get_chat_id <BOT_TOKEN>
"""
import sys

import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    r = requests.get(f"https://api.telegram.org/bot{sys.argv[1]}/getUpdates", timeout=30).json()
    if not r.get("ok"):
        sys.exit(f"Telegram error: {r}")
    chats = {}
    for u in r["result"]:
        msg = u.get("message") or u.get("channel_post") or {}
        if "chat" in msg:
            c = msg["chat"]
            chats[c["id"]] = c.get("username") or c.get("title") or c.get("first_name")
    if not chats:
        sys.exit("No messages yet: send something to the bot first, then run again.")
    for cid, name in chats.items():
        print(f"{cid}\t{name}")


if __name__ == "__main__":
    main()
