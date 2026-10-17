"""Decide whether a listing matches the search and how to label it."""
import math
import re
from dataclasses import dataclass, field
from datetime import datetime

from .models import Listing

# Clear signs of photovoltaic panels that generate electricity.
PV_STRONG = [
    r"photo[\s-]?voltaic",
    r"\bP\.?V\.?\b(?!C)",                       # "PV", "P.V." but not "PVC"
    r"\bPV[\s-]?(system|panels?|installation)",
    r"φωτοβολτα",                               # Greek
    r"фото\s?-?вольта", r"фотоэлектр",          # Russian
    r"солнечн\w*\s+(электро|станц|генерац)",
    r"net[\s-]?metering",
    r"solar\s+(power|electricity|energy\s+system|generat\w*|plant|pv)",
    r"solar\s+panels?\s+(for|producing|generating)\s+(the\s+)?(electric|power|energy)",
    r"(electric\w*|power)\s+(from|by|via)\s+solar",
    r"\d+(\.\d+)?\s?kw[p]?\b[^.]{0,40}solar|solar[^.]{0,40}\d+(\.\d+)?\s?kw[p]?\b",
    r"(reduced|low|lower|minimal|zero)\s+(electricity|electric|power)\s+bills?[^.]{0,60}solar"
    r"|solar[^.]{0,60}(reduced|low|lower|minimal|zero)\s+(electricity|electric|power)\s+bills?",
]

# "Solar" mentioned, but it may be just the water heater.
SOLAR_ANY = [r"\bsolar\b", r"ηλιακ", r"солнечн"]

# Solar used for hot water only.
SOLAR_WATER = [
    r"solar\s+(water|heater|boiler|hot\s+water|thermosiphon)",
    r"water\s+solar(\s+(system|panels?|heater))?",
    r"solar[^.]{0,30}(water\s+heat\w*|hot\s+water|boiler)",
    r"(water\s+heat\w*|hot\s+water|boiler)[^.]{0,30}solar",
    r"ηλιακ\w*\s+θερμοσ", r"θερμοσίφων",
    r"солнечн\w*\s+(водонагрев|бойлер|нагрев\w*\s+вод)",
]

NEW_BUILD = [
    r"brand[\s-]?new", r"newly[\s-]?built", r"new[\s-]?build", r"new\s+(building|development|project)",
    r"under\s+construction", r"νεόδμητ", r"καινούργι", r"новостро", r"новый\s+дом",
]
YEAR_IN_TEXT = r"(?:built|constructed|completed|construction|built\s+in|year)\D{0,15}(20[0-3]\d|19\d\d)"


PV_COMMUNAL = r"(photo[\s-]?voltaic|\bPV\b|solar)[^.]{0,80}(communal|common)\s+(area|part|space)s?"


def _any(patterns, text):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def distance_km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (0.5 - math.cos((lat2 - lat1) * p) / 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2)
    return 12742 * math.asin(math.sqrt(a))


def pv_status(text: str) -> str:
    """'yes' (PV for electricity), 'unclear' (solar mentioned, kind unknown) or 'no'."""
    if _any(PV_STRONG, text):
        return "yes"
    if not _any(SOLAR_ANY, text):
        return "no"
    # Drop every solar-water phrase and see if any other "solar" mention remains.
    stripped = text
    for p in SOLAR_WATER:
        stripped = re.sub(p, " ", stripped, flags=re.IGNORECASE)
    return "unclear" if _any(SOLAR_ANY, stripped) else "no"


def build_year(listing: Listing) -> tuple[int | None, bool]:
    """Return (year, looks_new). Year comes from the listing field or the text."""
    if listing.build_year:
        return listing.build_year, False
    text = f"{listing.title}\n{listing.description}"
    m = re.search(YEAR_IN_TEXT, text, re.IGNORECASE)
    if m:
        year = int(m.group(1))
        if 1950 <= year <= datetime.now().year + 3:
            return year, False
    return None, _any(NEW_BUILD, text)


@dataclass
class Verdict:
    match: bool
    tier: str = ""           # "base" | "pv"
    pv: str = "no"
    year: int | None = None
    distance: float | None = None   # km from the configured centre
    flags: list[str] = field(default_factory=list)
    reason: str = ""


def evaluate(listing: Listing, cfg: dict) -> Verdict:
    s = cfg["search"]
    text = f"{listing.title}\n{listing.description}"
    flags = []

    if listing.price is None:
        return Verdict(False, reason="no price")
    if listing.bedrooms is not None and listing.bedrooms not in s["bedrooms"]:
        return Verdict(False, reason=f"bedrooms {listing.bedrooms}")

    dist = None
    if listing.lat and listing.lon and s.get("center"):
        dist = distance_km(listing.lat, listing.lon, *s["center"])
        if dist > s["max_distance_km"]:
            return Verdict(False, reason=f"distance {dist:.1f} km")
    elif s.get("center"):
        flags.append("нет координат")

    if listing.area is None:
        flags.append("площадь не указана")
    elif listing.area < s["min_area_m2"]:
        return Verdict(False, reason=f"area {listing.area}")

    year, looks_new = build_year(listing)
    if year is not None and year < s["min_build_year"]:
        return Verdict(False, reason=f"year {year}")
    if year is None:
        flags.append("похоже, новостройка" if looks_new else "год постройки не указан")

    pv = pv_status(text)
    if s.get("require_pv") and pv != "yes":
        return Verdict(False, reason=f"no PV ({pv})")
    if listing.price <= s["base_max_price"]:
        tier = "base"
    elif listing.price <= s["pv_max_price"]:
        if pv == "yes":
            tier = "pv"
        elif pv == "unclear" and s.get("send_unclear_solar", True):
            tier = "pv"
            flags.append("solar упомянут — уточнить, PV или бойлер")
        else:
            return Verdict(False, reason=f"price {listing.price} without PV")
    else:
        return Verdict(False, reason=f"price {listing.price}")
    if pv == "yes" and re.search(PV_COMMUNAL, text, re.IGNORECASE):
        flags.append("PV, возможно, только для общих зон дома")

    return Verdict(True, tier=tier, pv=pv, year=year, distance=dist, flags=flags)
