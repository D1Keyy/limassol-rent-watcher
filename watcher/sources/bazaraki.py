"""Bazaraki: uses the JSON API the website itself calls."""
import logging
from datetime import datetime, timezone

import requests

from ..models import Listing

API = "https://www.bazaraki.com/api/items/"
CITY_IDS = {"limassol": 12, "nicosia": 11, "larnaca": 13, "paphos": 14, "famagusta": 15}
FURNISHING = {"1": "с мебелью", "2": "частично с мебелью", "3": "без мебели", "4": "только техника"}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
           "Accept": "application/json"}

log = logging.getLogger(__name__)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_listing(r: dict) -> Listing:
    a = r.get("attrs") or {}
    beds = a.get("attrs__number-of-bedrooms")
    year = a.get("attrs__construction-year")
    images = r.get("images") or []
    coords = r.get("coordinates") or {}
    return Listing(
        source="bazaraki",
        id=str(r["id"]),
        url=f"https://www.bazaraki.com/adv/{r['id']}_{r.get('slug', '')}/",
        title=(r.get("title") or "").strip(),
        price=_num(r.get("price")),
        bedrooms=int(beds) if str(beds).isdigit() else None,
        area=_num(a.get("attrs__area")),
        build_year=int(year) if str(year).isdigit() else None,
        description=r.get("description") or "",
        posted=_parse_dt(r.get("created_dt")),
        photo=images[0].get("url") if images else None,
        furnishing=FURNISHING.get(str(a.get("attrs__furnishing"))),
        lat=coords.get("latitude"),
        lon=coords.get("longitude"),
        extra={"postcode": a.get("attrs__postalcode")},
    )


def fetch(cfg: dict, stop_before: datetime, max_pages: int, seen: set[str]) -> list[Listing]:
    """Newest listings for every rubric, walking pages until `stop_before` or `max_pages`.

    Price/bedrooms/area are filtered server-side with loose bounds; the exact
    rules (tiers, PV, build year) are applied later in filters.evaluate().
    """
    s = cfg["search"]
    city = CITY_IDS[s["city"].lower()]
    out: list[Listing] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for rubric in cfg["sources"]["bazaraki"]["rubrics"]:
        params = [("rubric", rubric), ("city", city), ("ordering", "-created_dt"),
                  ("price_max", s["pv_max_price"]), ("attrs__area_min", s["min_area_m2"])]
        params += [("attrs__number-of-bedrooms", b) for b in s["bedrooms"]]
        # Listings with no area set are excluded by attrs__area_min, so also
        # run a pass without it and let filters.evaluate() flag them.
        for with_area in (True, False):
            p = params if with_area else [x for x in params if x[0] != "attrs__area_min"]
            for page in range(1, max_pages + 1):
                resp = session.get(API, params=p + [("page", page)], timeout=30)
                resp.raise_for_status()
                data = resp.json()
                items = [_to_listing(r) for r in data.get("results") or []]
                out.extend(i for i in items if with_area or i.area is None)
                dates = [i.posted for i in items if i.posted]
                if not items or (dates and min(dates) < stop_before) or not data.get("next"):
                    break
            log.info("bazaraki rubric %s (area filter %s): done", rubric, with_area)

    # De-duplicate (the two passes can overlap).
    return list({l.id: l for l in out}.values())
