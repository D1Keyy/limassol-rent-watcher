import html
import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
           "Accept-Language": "en-US,en;q=0.9"}

# Approximate centres of Limassol neighbourhoods, for sites that give an
# area name but no coordinates. Keys are lowercase, matched as substrings.
AREA_COORDS = {
    "old town": (34.674, 33.043), "historic": (34.674, 33.043), "city cent": (34.676, 33.043), "limassol centre": (34.676, 33.043),
    "limassol center": (34.676, 33.043), "katholiki": (34.672, 33.035),
    "neapol": (34.690, 33.055), "agia zoni": (34.690, 33.035), "ayia zoni": (34.690, 33.035),
    "agios nikolaos": (34.676, 33.025), "zakaki": (34.665, 33.000), "omonia": (34.666, 33.015),
    "kapsalos": (34.693, 33.025), "mesa geitonia": (34.700, 33.045), "mesa gitonia": (34.700, 33.045),
    "agios athanasios": (34.712, 33.050), "agia fyla": (34.705, 33.025), "ayia fyla": (34.705, 33.025),
    "linopetra": (34.700, 33.075), "potamos germasogeia": (34.700, 33.085),
    "germasogeia": (34.708, 33.088), "germasogia": (34.708, 33.088), "yermasoyia": (34.708, 33.088),
    "mouttagiaka": (34.715, 33.115), "moutagiaka": (34.715, 33.115),
    "agios tychonas": (34.725, 33.135), "agios tychon": (34.725, 33.135), "tourist area": (34.700, 33.090),
    "pyrgos": (34.737, 33.185), "parekklisia": (34.745, 33.165), "moni": (34.725, 33.200),
    "ypsonas": (34.688, 32.960), "kato polemidia": (34.690, 33.005), "pano polemidia": (34.705, 33.000),
    "polemidia": (34.695, 33.003), "ekali": (34.680, 33.028), "tsirio": (34.688, 33.040),
    "agios ioannis": (34.684, 33.039), "agios spyridonas": (34.695, 33.050),
    "agios georgios": (34.700, 33.062), "enaerios": (34.678, 33.050), "palodia": (34.735, 33.020),
    "kolossi": (34.665, 32.930), "erimi": (34.672, 32.913), "trachoni": (34.630, 32.955),
    "asomatos": (34.620, 32.940), "akrotiri": (34.600, 32.960), "episkopi": (34.670, 32.880),
    "fasoula": (34.738, 32.990), "mathikoloni": (34.735, 33.020), "spitali": (34.750, 32.950),
    "souni": (34.727, 32.885), "kalogiri": (34.740, 33.030), "foinikaria": (34.755, 33.100),
}


def locate(text: str) -> tuple[float, float] | None:
    t = text.lower()
    # Longest key first so "kato polemidia" wins over "polemidia".
    for key in sorted(AREA_COORDS, key=len, reverse=True):
        if key in t:
            return AREA_COORDS[key]
    return None


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def html_to_text(s: str) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def number(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"\d[\d,.]*", s)
    return float(m.group(0).replace(",", "")) if m else None
