"""Jinja2-based static site generator.

Produces a complete static site from parsed documentation.
"""

import datetime
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .parser import ParsedDoc

log = logging.getLogger(__name__)

# Locate templates and static dirs relative to this package file
_PKG_DIR = Path(__file__).parent
TEMPLATES_DIR = _PKG_DIR / "templates"
STATIC_DIR = _PKG_DIR / "static"

_SLUG_RE = re.compile(r"[^\w\s-]")
_COLLAPSE_RE = re.compile(r"[\s_]+")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = _SLUG_RE.sub("", text)
    text = _COLLAPSE_RE.sub("-", text)
    return text.strip("-") or "unnamed"


# ── Nav model ─────────────────────────────────────────────────────────────────

@dataclass
class NavDoc:
    title: str
    url: str       # relative to site root
    description: str = ""


@dataclass
class NavSource:
    name: str
    slug: str
    category: str
    type: str         # local | remote
    path: str
    description: str
    backup_enabled: bool
    index_url: str
    doc_count: int = 0
    last_synced: str = ""
    docs: list[NavDoc] = field(default_factory=list)


@dataclass
class NavCategory:
    name: str
    sources: list[NavSource] = field(default_factory=list)


# ── Site context builder ───────────────────────────────────────────────────────

def _build_nav(config: dict, docs_by_source: dict[str, list[ParsedDoc]]) -> list[NavCategory]:
    """Build the navigation tree from config sources and parsed docs."""
    categories: dict[str, NavCategory] = {}

    for src in config.get("sources", []):
        cat_name = src.get("category", "General")
        name = src.get("name", "Unnamed")
        slug = _slugify(name)
        cat_slug = _slugify(cat_name)
        index_url = f"{cat_slug}/{slug}/index.html"

        source_docs = docs_by_source.get(name, [])
        source_docs_sorted = sorted(source_docs, key=lambda d: (d.order, d.title))

        nav_docs = [
            NavDoc(
                title=d.title,
                url=f"{cat_slug}/{slug}/{_slugify(d.title)}.html",
                description=d.description,
            )
            for d in source_docs_sorted
        ]

        nav_source = NavSource(
            name=name,
            slug=slug,
            category=cat_name,
            type=src.get("type", "local"),
            path=src.get("path", ""),
            description=src.get("description", ""),
            backup_enabled=src.get("backup", {}).get("enabled", False),
            index_url=index_url,
            doc_count=len(nav_docs),
            docs=nav_docs,
        )

        if cat_name not in categories:
            categories[cat_name] = NavCategory(name=cat_name)
        categories[cat_name].sources.append(nav_source)

    return list(categories.values())


# ── Jinja2 environment ─────────────────────────────────────────────────────────

def _make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


# ── Generator ─────────────────────────────────────────────────────────────────

class SiteGenerator:
    """Generates the full static site from config and parsed documents."""

    def __init__(self, config: dict, docs: list[ParsedDoc]) -> None:
        self._config = config
        self._all_docs = docs

        site_cfg = config.get("site", {})
        self._output_dir = Path(site_cfg.get("output_dir", "/tmp/docsync-out"))
        self._site_title = site_cfg.get("title", "DocSync Wiki")

        # Group docs by source name
        self._docs_by_source: dict[str, list[ParsedDoc]] = {}
        for doc in docs:
            self._docs_by_source.setdefault(doc.source_name, []).append(doc)

        self._nav = _build_nav(config, self._docs_by_source)
        self._env = _make_env()
        self._last_synced = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Shared template context ────────────────────────────────────────────────

    def _base_ctx(
        self,
        *,
        root_path: str = "",
        current_page: str = "",
        current_source: str = "",
        current_doc_url: str = "",
    ) -> dict[str, Any]:
        return {
            "site_title": self._site_title,
            "nav_categories": self._nav,
            "root_path": root_path,
            "current_page": current_page,
            "current_source": current_source,
            "current_doc_url": current_doc_url,
            "last_synced": self._last_synced,
            "page_title": "",
        }

    # ── File writing ───────────────────────────────────────────────────────────

    def _write(self, rel_path: str, html: str) -> None:
        out = self._output_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        log.debug("wrote %s", rel_path)

    def _render(self, template_name: str, ctx: dict) -> str:
        tmpl = self._env.get_template(template_name)
        return tmpl.render(**ctx)

    # ── Individual page generators ─────────────────────────────────────────────

    def _gen_index(self) -> None:
        from .backup.report import backup_status

        total_docs = sum(len(v) for v in self._docs_by_source.values())
        total_sources = sum(len(c.sources) for c in self._nav)

        try:
            bk_statuses = backup_status(self._config)
        except Exception:
            bk_statuses = []

        ctx = self._base_ctx(root_path="", current_page="home")
        ctx.update({
            "page_title": "Dashboard",
            "total_docs": total_docs,
            "total_sources": total_sources,
            "backup_statuses": bk_statuses,
        })
        self._write("index.html", self._render("index.html", ctx))

    def _gen_static_pages(self, recent_docs: Optional[list] = None) -> None:
        # Search page
        ctx = self._base_ctx(root_path="", current_page="search")
        ctx["page_title"] = "Search"
        ctx["total_docs"] = len(self._all_docs)
        self._write("search.html", self._render("search.html", ctx))

        # Updates page
        ctx = self._base_ctx(root_path="", current_page="updates")
        ctx["page_title"] = "Recent Updates"
        updates = []
        for doc in (recent_docs or [])[:50]:
            cat_slug = _slugify(
                next((c.name for c in self._nav
                      for s in c.sources if s.name == doc.source_name), "misc")
            )
            src_slug = _slugify(doc.source_name)
            updates.append({
                "title": doc.title,
                "source_name": doc.source_name,
                "rel_path": doc.rel_path,
                "url": f"{cat_slug}/{src_slug}/{_slugify(doc.title)}.html",
                "synced_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
        ctx["updates"] = updates
        self._write("updates.html", self._render("updates.html", ctx))

    def _gen_backups_pages(self) -> int:
        """Generate backups.html dashboard + per-source snapshot browser pages.

        Returns the number of pages written.
        """
        from .backup.report import (
            backup_status,
            recent_backup_events,
            snapshot_list,
            source_backup_dir,
        )
        from .utils import human_size

        backup_cfg = self._config.get("backup", {})
        base_dir_str = backup_cfg.get("base_dir")
        statuses = backup_status(self._config)
        events = recent_backup_events(self._config, n=20)

        # Storage gauge
        used_bytes = sum(s["total_size_bytes"] for s in statuses)
        max_gb = backup_cfg.get("max_total_size_gb", 0)
        max_bytes = int(max_gb * 1024 ** 3) if max_gb else 0
        pct_used = min(100, int(used_bytes / max_bytes * 100)) if max_bytes > 0 else 0

        # Alert banners
        alerts: list[dict] = []
        failed = [s for s in statuses if s["health"] == "err"]
        stale = [s for s in statuses if s["health"] == "warn" and s["snapshot_count"] > 0]
        if failed:
            alerts.append({
                "level": "err",
                "message": f"{len(failed)} source(s) failed last backup: "
                           + ", ".join(s["source_name"] for s in failed),
            })
        if stale:
            alerts.append({
                "level": "warn",
                "message": f"{len(stale)} source(s) have stale backups: "
                           + ", ".join(s["source_name"] for s in stale),
            })
        if max_bytes and pct_used >= 80:
            alerts.append({
                "level": "warn",
                "message": f"Storage at {pct_used}% of limit "
                           f"({human_size(used_bytes)} / {human_size(max_bytes)})",
            })

        # Main backups dashboard
        ctx = self._base_ctx(root_path="", current_page="backups")
        ctx.update({
            "page_title": "Backups",
            "backup_statuses": statuses,
            "backup_events": events,
            "storage_used_bytes": used_bytes,
            "storage_used_human": human_size(used_bytes),
            "storage_max_bytes": max_bytes,
            "storage_max_human": human_size(max_bytes) if max_bytes else "",
            "storage_pct": pct_used,
            "alerts": alerts,
        })
        self._write("backups.html", self._render("backups.html", ctx))
        pages = 1

        # Per-source snapshot browser pages
        backup_sources = [
            src for src in self._config.get("sources", [])
            if src.get("backup", {}).get("enabled", True)
        ]
        for src in backup_sources:
            name = src["name"]
            from .backup.report import _source_slug
            slug = _source_slug(name)

            snaps: list[dict] = []
            if base_dir_str:
                from pathlib import Path as _Path
                src_dir = source_backup_dir(_Path(base_dir_str).expanduser(), name)
                snaps = snapshot_list(src_dir) if src_dir.exists() else []

            # Find status entry for this source
            src_status = next((s for s in statuses if s["source_name"] == name), {})

            ctx = self._base_ctx(root_path="../", current_page="backups")
            ctx.update({
                "page_title": f"{name} — Snapshots",
                "source_name": name,
                "source_slug": slug,
                "source_type": src.get("type", "local"),
                "source_path": src.get("path", src.get("host", "")),
                "snapshots": snaps,
                "status": src_status,
            })
            self._write(f"backups/{slug}.html", self._render("backup_source.html", ctx))
            pages += 1

        return pages

    def _gen_project_page(self, nav_source: NavSource, source_docs: list[ParsedDoc]) -> None:
        cat_slug = _slugify(nav_source.category)
        src_slug = nav_source.slug
        root_path = "../../"

        docs_sorted = sorted(source_docs, key=lambda d: (d.order, d.title))
        doc_list = [
            {
                "title": d.title,
                "description": d.description,
                "url": f"{cat_slug}/{src_slug}/{_slugify(d.title)}.html",
                "tags": d.tags,
                "rel_path": d.rel_path,
            }
            for d in docs_sorted
        ]

        ctx = self._base_ctx(
            root_path=root_path,
            current_source=nav_source.name,
        )
        ctx.update({
            "page_title": nav_source.name,
            "source": {
                "name": nav_source.name,
                "category": nav_source.category,
                "type": nav_source.type,
                "path": nav_source.path,
                "backup_enabled": nav_source.backup_enabled,
                "doc_count": len(source_docs),
                "index_url": nav_source.index_url,
            },
            "docs": doc_list,
        })
        self._write(
            f"{cat_slug}/{src_slug}/index.html",
            self._render("project.html", ctx),
        )

    def _gen_doc_page(
        self,
        doc: ParsedDoc,
        nav_source: NavSource,
        prev_doc: Optional[ParsedDoc],
        next_doc: Optional[ParsedDoc],
    ) -> str:
        """Generate one doc page; returns the relative output path."""
        cat_slug = _slugify(nav_source.category)
        src_slug = nav_source.slug
        doc_slug = _slugify(doc.title)
        rel_out = f"{cat_slug}/{src_slug}/{doc_slug}.html"
        root_path = "../../"

        def nav_entry(d: Optional[ParsedDoc]) -> Optional[dict]:
            if d is None:
                return None
            return {
                "title": d.title,
                "url": f"{cat_slug}/{src_slug}/{_slugify(d.title)}.html",
            }

        ctx = self._base_ctx(
            root_path=root_path,
            current_source=nav_source.name,
            current_doc_url=rel_out,
        )
        ctx.update({
            "page_title": doc.title,
            "doc": doc,
            "source": {
                "name": nav_source.name,
                "category": nav_source.category,
                "index_url": nav_source.index_url,
            },
            "prev_doc": nav_entry(prev_doc),
            "next_doc": nav_entry(next_doc),
        })
        self._write(rel_out, self._render("doc.html", ctx))
        return rel_out

    # ── Static assets ──────────────────────────────────────────────────────────

    def _copy_assets(self) -> None:
        assets_dir = self._output_dir / "assets"
        if assets_dir.exists():
            shutil.rmtree(assets_dir)
        if STATIC_DIR.exists():
            shutil.copytree(STATIC_DIR, assets_dir)
            log.debug("copied assets to %s", assets_dir)
        else:
            log.warning("Static assets directory not found: %s", STATIC_DIR)

    # ── Main entry point ───────────────────────────────────────────────────────

    def generate(self, recent_docs: Optional[list] = None) -> int:
        """Generate the full site. Returns number of pages written."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        pages = 0

        self._copy_assets()

        self._gen_index()
        pages += 1

        self._gen_static_pages(recent_docs)
        pages += 2  # search, updates

        pages += self._gen_backups_pages()  # backups.html + per-source pages

        # Search index
        from .search import build_index, write_index
        index_entries = build_index(self._all_docs, self._nav)
        write_index(index_entries, self._output_dir)

        # Backup status JSON
        from .backup.report import backup_status_json
        try:
            backup_status_json(self._config, self._output_dir)
        except Exception as exc:
            log.debug("backup-status.json skipped: %s", exc)

        # Per-source project and doc pages
        for nav_cat in self._nav:
            for nav_source in nav_cat.sources:
                source_docs = self._docs_by_source.get(nav_source.name, [])
                source_docs_sorted = sorted(source_docs, key=lambda d: (d.order, d.title))

                self._gen_project_page(nav_source, source_docs_sorted)
                pages += 1

                for i, doc in enumerate(source_docs_sorted):
                    prev_d = source_docs_sorted[i - 1] if i > 0 else None
                    next_d = source_docs_sorted[i + 1] if i < len(source_docs_sorted) - 1 else None
                    self._gen_doc_page(doc, nav_source, prev_d, next_d)
                    pages += 1

        log.info("Site generated: %d pages → %s", pages, self._output_dir)
        return pages


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_site(
    config: dict,
    docs: list[ParsedDoc],
    recent_docs: Optional[list] = None,
) -> int:
    """Generate the static site. Returns page count."""
    gen = SiteGenerator(config, docs)
    return gen.generate(recent_docs=recent_docs)
