"""One check: fetch all sources, filter, send new matches to Telegram, save state.

Run:  python -m watcher.main            (needs TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
      python -m watcher.main --dry-run  (prints matches, sends and saves nothing)
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

try:  # use the OS certificate store (fixes SSL errors with some Windows Python installs)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from .filters import evaluate
from .sources import SOURCES
from .telegram import Telegram, format_message

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "state" / "seen.json"
KEEP_DAYS = 90            # forget listings after this long
FAIL_ALERT_AFTER = 4      # consecutive failed runs of a source before alerting (~1 hour)

log = logging.getLogger("watcher")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"last_run": None, "seen": {}, "failures": {}}


def save_state(state: dict) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    state["seen"] = {k: v for k, v in state["seen"].items() if v["first_seen"] >= cutoff}
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=0, sort_keys=True),
                          encoding="utf-8")


def run(dry_run: bool) -> int:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    state = load_state()
    now = datetime.now(timezone.utc)
    first_run = not state["last_run"]

    if first_run:
        stop_before = now - timedelta(days=cfg["notify"]["initial_backfill_days"])
        max_pages = 40
    else:
        # Overlap with the previous run so late-indexed listings are not missed.
        stop_before = datetime.fromisoformat(state["last_run"]) - timedelta(hours=6)
        max_pages = 10

    tg = None
    if not dry_run:
        token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat:
            log.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set (or use --dry-run)")
            return 2
        tg = Telegram(token, chat)

    to_send = []   # (listing, verdict, old_price)
    for name, module in SOURCES.items():
        if not cfg["sources"].get(name, {}).get("enabled"):
            continue
        try:
            listings = module.fetch(cfg, stop_before, max_pages, set(state["seen"]))
            state["failures"][name] = 0
        except Exception as e:  # one broken source must not stop the others
            n = state["failures"].get(name, 0) + 1
            state["failures"][name] = n
            log.exception("source %s failed (%d in a row)", name, n)
            if tg and n == FAIL_ALERT_AFTER:
                tg.send(f"⚠️ Источник <b>{name}</b> не отвечает уже {n} проверок подряд: "
                        f"<code>{type(e).__name__}: {str(e)[:200]}</code>")
            continue

        log.info("%s: %d listings fetched", name, len(listings))
        for l in listings:
            v = evaluate(l, cfg)
            prev = state["seen"].get(l.key)
            if prev is None:
                state["seen"][l.key] = {"first_seen": now.isoformat(), "price": l.price}
                # Sites without date sorting may return old ads on the first run.
                too_old = first_run and l.posted and l.posted < stop_before
                if v.match and not too_old:
                    to_send.append((l, v, None))
            else:
                old = prev.get("price")
                if (cfg["notify"].get("price_drops") and v.match and old and l.price
                        and l.price < old):
                    to_send.append((l, v, old))
                prev["price"] = l.price

    to_send.sort(key=lambda t: t[0].posted or now)
    log.info("%d matches to send", len(to_send))
    for l, v, old in to_send:
        text = format_message(l, v, price_drop_from=old)
        if dry_run:
            print(text, "\n" + "-" * 40)
        else:
            tg.send(text, preview_url=l.url)
            time.sleep(1.1)  # stay under Telegram's per-chat rate limit

    if not dry_run:
        state["last_run"] = now.isoformat()
        save_state(state)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print matches, send/save nothing")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(run(args.dry_run))


if __name__ == "__main__":
    main()
