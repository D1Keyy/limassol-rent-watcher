"""index.cy: HTML search (has price filter) + WordPress REST API (full text, exact date)."""
import logging
import re
from datetime import datetime, timezone

from ..models import Listing
from .common import html_to_text, locate, number, session

SEARCH = "https://index.cy/for-rent/{kind}/{city}/"
REST = "https://index.cy/wp-json/wp/v2/rent"
KINDS = ("apartments-flats", "houses")
CARD = re.compile(r'<article class="lv2-lcard sv2-card" data-id="(\d+)">(.*?)</article>', re.S)

log = logging.getLogger(__name__)


def _card(m: re.Match) -> Listing:
    body = re.sub(r"<svg.*?</svg>", "", m.group(2), flags=re.S)
    link = re.search(r'href="(https://index\.cy/rent/[^"]+)"[^>]*class="lv2-lcard-title">(.*?)</a>', body, re.S)
    price = re.search(r'lv2-price-row"><strong>([^<]+)', body)
    beds = re.search(r'title="Bedrooms">(\d+)', body)
    area = re.search(r'title="Covered area">([^<]+)', body)
    approx = re.search(r'class="sv2-approx"[^>]*>(.*?)</div>', body, re.S)
    excerpt = re.search(r'class="sv2-excerpt">(.*?)</p>', body, re.S)
    img = re.search(r'<img src="([^"]+)"', body)
    title = html_to_text(link.group(2)) if link else ""
    loc = html_to_text(approx.group(1)).replace("Approximate ·", "").strip() if approx else None
    if not loc and "–" in title:
        loc = title.rsplit("–", 1)[1].strip()
    return Listing(
        source="index.cy", id=m.group(1), url=link.group(1) if link else "", title=title,
        price=number(price.group(1)) if price else None,
        bedrooms=int(beds.group(1)) if beds else None,
        area=number(area.group(1)) if area else None, build_year=None,
        description=html_to_text(excerpt.group(1)) if excerpt else "", posted=None,
        photo=img.group(1) if img else None, location=loc,
    )


def fetch(cfg: dict, stop_before: datetime, max_pages: int, seen: set[str]) -> list[Listing]:
    s_cfg = cfg["search"]
    s = session()
    beds = ",".join(str(b) for b in s_cfg["bedrooms"] if b > 0)
    out = []
    for kind in KINDS:
        url = SEARCH.format(kind=kind, city=s_cfg["city"].lower())
        for page in range(1, max_pages + 1):
            params = {"sort": "latest", "price": f"0..{s_cfg['pv_max_price']}", "bedrooms": beds}
            if page > 1:
                params["pg"] = page
            resp = s.get(url, params=params, timeout=30)
            resp.raise_for_status()
            cards = [_card(m) for m in CARD.finditer(resp.text)]
            new = [c for c in cards if c.key not in seen]
            if new:
                # Full description and exact publish date for the new ones.
                r = s.get(REST, params={"include": ",".join(c.id for c in new), "per_page": 100,
                                        "_fields": "id,date_gmt,content"}, timeout=30)
                r.raise_for_status()
                full = {str(x["id"]): x for x in r.json()}
                for c in new:
                    x = full.get(c.id)
                    if x:
                        c.description = html_to_text(x["content"]["rendered"]) or c.description
                        c.posted = datetime.fromisoformat(x["date_gmt"]).replace(tzinfo=timezone.utc)
            for c in cards:
                if c.location:
                    c.lat, c.lon = locate(c.location) or (None, None)
                    c.extra["approx_coords"] = c.lat is not None
            out.extend(cards)
            dates = [c.posted for c in new if c.posted]
            if len(cards) < 24 or not new or (dates and max(dates) < stop_before):
                break
        log.info("index.cy %s: done", kind)
    return out
