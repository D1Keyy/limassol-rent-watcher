"""Print the chat id of whoever last wrote to the bot.

1. Open your bot in Telegram and send it any message (e.g. /start).
2. python -m watcher.get_chat_id   (asks for the token)
"""
import getpass
import sys

import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


def main() -> None:
    # Without an argument, ask for the token so it doesn't end up in shell history.
    token = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("Bot token (hidden): ").strip()
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
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
