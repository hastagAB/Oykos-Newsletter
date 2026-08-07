"""Event source registry - the monitoring map from the PLS events spreadsheet.

The spreadsheet is the crawler configuration, not the content. Each row says
where to look, how often, and what a relevant event looks like there. The event
details themselves always come from the live page.

Two thirds of the rows point at a homepage rather than an event listing, so the
crawler needs a discovery stage before extraction. ``EventSource.needs_discovery``
marks those.
"""
from __future__ import annotations

import csv
import logging
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Priorita_bot 1 sources are always crawled; lower priorities rotate.
ALWAYS_CRAWL_PRIORITY = 1

_LISTING_MARKER = "elenco eventi"
_HIGH_RELEVANCE = "alta"


@dataclass(frozen=True)
class EventSource:
    """One crawl target from the registry."""

    source_id: str
    name: str
    acronym: str
    category: str
    url: str
    secondary_url: str
    page_type: str
    domain: str
    relevance: str
    priority: int
    check_frequency: str
    keywords: tuple[str, ...]
    extraction_method: str
    notes: str

    @property
    def needs_discovery(self) -> bool:
        """True when the URL is a homepage and the event listing must be found."""
        return _LISTING_MARKER not in self.page_type.lower()

    @property
    def is_high_relevance(self) -> bool:
        return self.relevance.strip().lower() == _HIGH_RELEVANCE

    @property
    def prefers_rss(self) -> bool:
        return "rss" in self.extraction_method.lower()

    @property
    def start_urls(self) -> tuple[str, ...]:
        """Every URL worth trying for this source, best first.

        When the row already points at a listing page, that is the best start.
        When it points at a homepage, the secondary URL is often the real event
        page the editorial team found by hand, so it is tried first.
        """
        ordered = (
            (self.url, self.secondary_url)
            if not self.needs_discovery
            else (self.secondary_url, self.url)
        )
        return tuple(dict.fromkeys(u for u in ordered if u.startswith("http")))


def _cell_values(path: Path) -> list[list[str]]:
    """Read the first worksheet of an xlsx into rows of strings."""
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            # The registry is an editorial file kept in the repository, not
            # remote input, so stdlib XML parsing is acceptable here.
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))  # noqa: S314
            shared = [
                "".join(t.text or "" for t in si.iter(f"{{{SPREADSHEET_NS}}}t"))
                for si in root.findall(f"{{{SPREADSHEET_NS}}}si")
            ]
        sheets = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet"))
        if not sheets:
            return []
        root = ET.fromstring(zf.read(sheets[0]))  # noqa: S314

    rows: list[list[str]] = []
    for row in root.iter(f"{{{SPREADSHEET_NS}}}row"):
        values: list[str] = []
        for cell in row.iter(f"{{{SPREADSHEET_NS}}}c"):
            node = cell.find(f"{{{SPREADSHEET_NS}}}v")
            raw = node.text if node is not None else ""
            if cell.get("t") == "s" and raw is not None:
                raw = shared[int(raw)]
            values.append((raw or "").strip())
        rows.append(values)
    return rows


def _split_keywords(raw: str) -> tuple[str, ...]:
    return tuple(k.strip().lower() for k in raw.split(";") if k.strip())


def _to_int(raw: str, default: int = 3) -> int:
    try:
        return int(float(raw))
    except ValueError:
        return default


def load_event_sources(path: Path) -> list[EventSource]:
    """Load the registry from the xlsx or csv the editorial team maintains."""
    if not path.exists():
        logger.warning("Event source registry not found at %s", path)
        return []

    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [list(r) for r in csv.reader(handle)]
    else:
        rows = _cell_values(path)

    if not rows:
        return []

    header = {name.strip(): index for index, name in enumerate(rows[0])}

    def cell(row: list[str], column: str) -> str:
        index = header.get(column)
        if index is None or index >= len(row):
            return ""
        return row[index].strip()

    sources: list[EventSource] = []
    for row in rows[1:]:
        source_id = cell(row, "ID_fonte")
        if not source_id:
            continue
        sources.append(
            EventSource(
                source_id=source_id,
                name=cell(row, "Nome_fonte"),
                acronym=cell(row, "Acronimo"),
                category=cell(row, "Categoria_fonte"),
                url=cell(row, "URL_da_monitorare"),
                secondary_url=cell(row, "URL_secondario"),
                page_type=cell(row, "Tipo_pagina"),
                domain=cell(row, "Dominio"),
                relevance=cell(row, "Rilevanza_PLS"),
                priority=_to_int(cell(row, "Priorita_bot")),
                check_frequency=cell(row, "Frequenza_check"),
                keywords=_split_keywords(cell(row, "Keyword_filtro")),
                extraction_method=cell(row, "Metodo_estrazione_consigliato"),
                notes=cell(row, "Note_operative"),
            ),
        )

    logger.info("Loaded %d event sources from %s", len(sources), path.name)
    return sources


@lru_cache(maxsize=1)
def get_event_sources(registry_path: str) -> tuple[EventSource, ...]:
    return tuple(load_event_sources(Path(registry_path)))


def select_for_run(
    sources: list[EventSource] | tuple[EventSource, ...],
    max_sources: int,
    *,
    offset: int = 0,
) -> list[EventSource]:
    """Choose which sources to crawl this week.

    Priority 1 sources run every week, as the feedback requires. The rest
    rotate, so 81 registry rows do not all get hit on every run.
    """
    always = [s for s in sources if s.priority <= ALWAYS_CRAWL_PRIORITY]
    rotating = [s for s in sources if s.priority > ALWAYS_CRAWL_PRIORITY]

    remaining = max(0, max_sources - len(always))
    if not rotating or remaining == 0:
        return always[:max_sources]

    start = offset % len(rotating)
    window = (rotating + rotating)[start : start + remaining]
    return always + window
