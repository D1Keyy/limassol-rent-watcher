from . import bazaraki, homecy, indexcy, rera

# config name -> module with fetch(cfg, stop_before, max_pages, seen) -> list[Listing]
SOURCES = {
    "bazaraki": bazaraki,
    "rera": rera,
    "homecy": homecy,
    "indexcy": indexcy,
}
