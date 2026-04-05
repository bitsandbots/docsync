"""Lunr.js search index builder.

Generates search-index.json consumed by the client-side search page.
"""

import json
import re
from pathlib import Path

from .parser import ParsedDoc


def _plain_text(html: str) -> str:
    """Strip HTML tags to produce plain text for indexing."""
    return re.sub(r"<[^>]+>", " ", html)


def build_index(docs: list[ParsedDoc], nav_categories: list) -> list[dict]:
    """Build a list of search documents suitable for Lunr.js.

    Each entry has: id, title, body (plain text), tags, url.
    """
    from .generator import _slugify

    # Build url lookup from nav
    url_map: dict[tuple[str, str], str] = {}
    for cat in nav_categories:
        for src in cat.sources:
            for doc in src.docs:
                url_map[(src.name, doc.title)] = doc.url

    entries = []
    for i, doc in enumerate(docs):
        url = url_map.get((doc.source_name, doc.title), "")
        entries.append({
            "id": i,
            "title": doc.title,
            "body": _plain_text(doc.html_body)[:2000],  # cap for index size
            "tags": " ".join(doc.tags),
            "source": doc.source_name,
            "url": url,
        })
    return entries


def write_index(entries: list[dict], output_dir: Path) -> None:
    """Write search-index.json to the site output directory."""
    out = output_dir / "search-index.json"
    out.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
