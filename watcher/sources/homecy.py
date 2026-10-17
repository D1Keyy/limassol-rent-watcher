"""home.cy: server-rendered search pages + one detail page per new listing."""
import logging
import re
import time
from datetime import datetime, timezone

from ..models import Listing
from .common import html_to_text, locate, number, session

BASE = "https://home.cy"
AREA_IDS = {"limassol": 11}
MAX_DETAILS = 12          # detail pages per run; home.cy shows a robot check if we go faster
DELAY = 2.0
ROBOT_CHECK = "Verify you are not a robot"
CARD = re.compile(r'<a class="whole" href="(/real-estate-to-rent/[^"]+-(\d+))"(.*?)class="favorite"', re.S)

log = logging.getLogger(__name__)


class Blocked(Exception):
    pass


def _card(m: re.Match) -> Listing:
    body = m.group(3)
    specs = re.findall(r"<li>([^<]+)</li>", body)
    beds = next((number(s) for s in specs if "bed" in s), None)
    area = next((number(s) for s in specs if "m²" in s), None)
    price = re.search(r'class="price">([^<]+)', body)
    loc = re.search(r'class="location">(.*?)</div>', body, re.S)
    img = re.search(r'src="(https://cdn\.cy/[^"]+)"', body)
    return Listing(
        source="home.cy", id=m.group(2), url=BASE + m.group(1), title="",
        price=number(price.group(1)) if price else None,
        bedrooms=int(beds) if beds is not None else None, area=area, build_year=None,
        description="", posted=None, photo=img.group(1) if img else None,
        location=re.sub(r"\s+", " ", html_to_text(loc.group(1))) if loc else None,
    )


def _detail(s, l: Listing) -> None:
    t = s.get(l.url, timeout=30).text
    if ROBOT_CHECK in t:
        raise Blocked(l.url)
    h1 = re.search(r"<h1>(.*?)</h1>", t, re.S)
    desc = re.search(r'<div class="text-preview[^"]*">(.*?)</div>', t, re.S)
    pub = re.search(r"Published:</span>\s*<span>([^<]+)</span>", t)
    text = html_to_text(t)
    year = re.search(r"Year built\s*(\d{4})", text)
    furn = re.search(r"Furnished\s*(Yes|No|Fully|Partially|Semi[^\n ]*)", text)
    l.title = html_to_text(h1.group(1)) if h1 else l.title
    l.description = html_to_text(desc.group(1)) if desc else ""
    if pub:
        try:
            l.posted = datetime.strptime(pub.group(1).strip(), "%d %b %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if year:
        l.build_year = int(year.group(1))
    if furn:
        f = furn.group(1).lower()
        l.furnishing = "без мебели" if f == "no" else "частично с мебелью" if f.startswith(("part", "semi")) else "с мебелью"
    l.extra["date_only"] = True


def fetch(cfg: dict, stop_before: datetime, max_pages: int, seen: set[str]) -> list[Listing]:
    s_cfg = cfg["search"]
    area_id = AREA_IDS[s_cfg["city"].lower()]
    s = session()
    beds = [b for b in s_cfg["bedrooms"]]
    out = []
    details = 0
    for ptype in ("apartment", "house"):
        params = {"type": ptype, "area[]": area_id, "bedrooms_min": min(beds), "bedrooms_max": max(beds),
                  "price_max": s_cfg["pv_max_price"], "sort": "relevance_desc"}
        for page in range(1, max_pages + 1):
            resp = s.get(f"{BASE}/real-estate-to-rent", params={**params, "p": page}, timeout=30)
            resp.raise_for_status()
            if ROBOT_CHECK in resp.text:
                if out:   # keep what we already have; the rest comes next run
                    log.warning("home.cy: robot check, stopping early")
                    return out
                raise Blocked("search page shows a robot check")
            cards = [_card(m) for m in CARD.finditer(resp.text)]
            new = [c for c in cards if c.key not in seen]
            ready = [c for c in cards if c.key in seen]
            for c in new:
                # Only open the detail page if the card itself could still match.
                if c.area is not None and c.area < s_cfg["min_area_m2"]:
                    ready.append(c)
                    continue
                # New listings we couldn't open are left out (not marked seen),
                # so a later run picks them up.
                if details >= MAX_DETAILS:
                    continue
                try:
                    _detail(s, c)
                except Blocked:
                    log.warning("home.cy: robot check on detail page, stopping early")
                    return out + ready
                details += 1
                if c.location:
                    c.lat, c.lon = locate(c.location) or (None, None)
                    c.extra["approx_coords"] = c.lat is not None
                ready.append(c)
                time.sleep(DELAY)
            out.extend(ready)
            dates = [c.posted for c in new if c.posted]
            if (len(cards) < 16 or not new or details >= MAX_DETAILS
                    or (dates and max(dates) < stop_before)):
                break
        log.info("home.cy %s: done", ptype)
    return out
