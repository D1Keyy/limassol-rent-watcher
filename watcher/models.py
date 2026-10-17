from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Listing:
    source: str
    id: str
    url: str
    title: str
    price: float | None
    bedrooms: int | None
    area: float | None
    build_year: int | None
    description: str
    posted: datetime | None
    photo: str | None = None
    furnishing: str | None = None
    lat: float | None = None
    lon: float | None = None
    location: str | None = None     # human-readable area, e.g. "Germasogeia, Limassol"
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"
