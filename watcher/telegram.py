"""Format listings and send them through the Telegram Bot API."""
import html
import logging
import time
from zoneinfo import ZoneInfo

import requests

from .filters import Verdict
from .models import Listing

CYPRUS = ZoneInfo("Asia/Nicosia")
log = logging.getLogger(__name__)


def format_message(l: Listing, v: Verdict, price_drop_from: float | None = None) -> str:
    if v.tier == "pv":
        badge = "☀️ <b>PV</b>" if v.pv == "yes" else "🌤 <b>solar?</b>"
    else:
        badge = "🏠" + (" ☀️ <b>PV</b>" if v.pv == "yes" else "")

    price = f"€{l.price:,.0f}".replace(",", " ")
    if price_drop_from:
        price = f"<s>€{price_drop_from:,.0f}</s> → {price}".replace(",", " ")
    head = [badge, f"<b>{price}</b>"]
    if l.bedrooms is not None:
        head.append("студия" if l.bedrooms == 0 else f"{l.bedrooms} сп.")
    if l.area:
        head.append(f"{l.area:.0f} м²")
    if v.year:
        head.append(f"{v.year} г.")

    lines = []
    if price_drop_from:
        lines.append("📉 <b>Цена снижена</b>")
    lines += [" · ".join(head), f"<b>{html.escape(l.title)}</b>"]

    info = []
    if l.location:
        info.append(f"🏘 {html.escape(l.location)}")
    if l.furnishing:
        info.append(f"🛋 {l.furnishing}")
    if l.lat and l.lon:
        pc = l.extra.get("postcode")
        approx = "~" if l.extra.get("approx_coords") else ""
        dist = f", {approx}{v.distance:.0f} км от центра" if v.distance is not None else ""
        info.append(f'📍 <a href="https://maps.google.com/?q={l.lat},{l.lon}">карта</a>'
                    + (f" ({pc}{dist})" if pc else f" ({dist[2:]})" if dist else ""))
    if info:
        lines.append(" · ".join(info))
    for f in v.flags:
        lines.append(f"⚠️ {html.escape(f)}")

    fmt = "%d.%m" if l.extra.get("date_only") else "%d.%m %H:%M"
    posted = (l.posted if l.extra.get("date_only") else l.posted.astimezone(CYPRUS)).strftime(fmt) if l.posted else ""
    lines.append(f'🔗 <a href="{html.escape(l.url)}">{l.source.capitalize()}</a>'
                 + (f" · {posted}" if posted else ""))
    return "\n".join(lines)


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.api = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

    def check(self) -> str | None:
        """None if the token and chat id work, otherwise Telegram's error text."""
        r = requests.post(f"{self.api}/getChat", json={"chat_id": self.chat_id}, timeout=30)
        return None if r.ok else f"{r.status_code}: {r.json().get('description', r.text[:200])}"

    def send(self, text: str, preview_url: str | None = None) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"url": preview_url, "prefer_large_media": True,
                                     "show_above_text": True} if preview_url
                                    else {"is_disabled": True},
        }
        for attempt in range(3):
            r = requests.post(f"{self.api}/sendMessage", json=payload, timeout=30)
            if r.ok:
                return True
            if r.status_code == 429:  # rate limit: wait as told
                time.sleep(r.json().get("parameters", {}).get("retry_after", 5) + 1)
                continue
            log.error("Telegram error %s: %s", r.status_code, r.text[:300])
            return False
        return False
