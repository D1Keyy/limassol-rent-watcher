"""RERA.cy: JSON API behind the rera.cy website (api.rera.cy)."""
import logging
import uuid
from datetime import datetime

import requests

from ..models import Listing
from .bazaraki import HEADERS

API = "https://api.rera.cy/api/v1/listings"
GEO_AREA_IDS = {"limassol": 434, "nicosia": None, "larnaca": None, "paphos": None}

log = logging.getLogger(__name__)


def _to_listing(r: dict) -> Listing:
    a = r.get("attributes") or {}
    beds = str(a.get("bedroom_type") or "")
    year = r.get("construction_year")
    coords = ((r.get("pin_map") or {}).get("location") or {}).get("coordinates") or []
    photos = r.get("photos") or []
    desc = ((r.get("translations") or {}).get("keys") or {}).get("description") or {}
    address = (r.get("pin_map") or {}).get("formatted_address") or ""
    return Listing(
        source="rera",
        id=str(r["id"]),
        url=f"https://rera.cy/property-search/listing-{r['slug']}",
        title=(r.get("title") or "").strip(),
        price=float(r["price"]) if r.get("price") else None,
        bedrooms=int(beds) if beds.isdigit() else None,
        area=float(r["full_area"]) if r.get("full_area") else None,
        build_year=int(year) if year else None,
        description=desc.get("en") or next(iter(desc.values()), "") if desc else "",
        posted=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) if r.get("created_at") else None,
        photo=photos[0].get("url") if photos else None,
        lon=coords[0] if len(coords) == 2 else None,
        lat=coords[1] if len(coords) == 2 else None,
        location=address.replace(", Cyprus", "") or None,
    )


def fetch(cfg: dict, stop_before: datetime, max_pages: int, seen: set[str]) -> list[Listing]:
    s = cfg["search"]
    area_id = GEO_AREA_IDS.get(s["city"].lower())
    if not area_id:
        raise ValueError(f"RERA: unknown city {s['city']}")
    headers = {**HEADERS, "X-Country": "CY", "X-Language": "en", "X-Session-Id": str(uuid.uuid4())}
    out: dict[str, Listing] = {}

    for rtype in ("flat", "house"):
        body = {"deal_type": "rent", "offer_type": "residential", "geo_area_ids": [area_id],
                "residential_type": [rtype], "rental_type": ["long_term"],
                "bedroom_type": [str(b) for b in s["bedrooms"] if b > 0],
                "price_to": s["pv_max_price"], "order": "created_at,desc"}
        for _ in range(max_pages):
            resp = requests.post(API, json=body, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()["data"]
            items = [_to_listing(r) for r in data.get("listings") or []]
            for i in items:
                out[i.id] = i
            # Promoted listings are ranked first, so a page's oldest item says
            # more than its first one.
            dates = [i.posted for i in items if i.posted]
            if not items or not data.get("next_cursor") or (dates and min(dates) < stop_before):
                break
            body["cursor"] = data["next_cursor"]
        log.info("rera %s: done", rtype)
    return list(out.values())
