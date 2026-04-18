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

# Max path length (POSIX standard is 255 for filename, 4096 for full path)
_MAX_FILENAME_LEN = 200
_MAX_PATH_LEN = 2000


def _path_slug(rel_path: str) -> str:
    """Derive a unique URL slug from a file's rel_path.

    Path components are joined with '--' so files named the same thing in
    different subdirectories (e.g. README.md appearing hundreds of times)
    each get a distinct URL rather than colliding on a title-derived slug.

    Examples:
        guide.md             → guide
        docs/guide.md        → docs--guide
        skills/foo/skill.md  → skills--foo--skill
    """
    path = Path(rel_path)
    parts = [_slugify(p) for p in (*path.parent.parts, path.stem) if p and p != "."]
    return "--".join(parts) or "unnamed"


def _slugify(text: str, *, truncate: bool = True) -> str:
    """Convert text to URL-safe slug.

    Args:
        text: Input text to slugify
        truncate: If True, truncate to MAX_FILENAME_LEN to avoid path issues
    """
    text = text.lower().strip()
    text = _SLUG_RE.sub("", text)
    text = _COLLAPSE_RE.sub("-", text)
    text = text.strip("-") or "unnamed"
    if truncate and len(text) > _MAX_FILENAME_LEN:
        # Truncate, keeping suffix for uniqueness
        text = text[: _MAX_FILENAME_LEN - 5] + "-" + text[-3:]
    return text


# ── Nav model ─────────────────────────────────────────────────────────────────


@dataclass
class NavDoc:
    title: str
    url: str  # relative to site root
    description: str = ""


@dataclass
class NavSource:
    name: str
    slug: str
    category: str
    type: str  # local | remote
    path: str
    description: str
    backup_enabled: bool
    index_url: str
    doc_count: int = 0
    last_synced: str = ""
    docs: list[NavDoc] = field(default_factory=list)
    readme_doc: Optional[NavDoc] = None
    primary_docs: list[NavDoc] = field(default_factory=list)
    additional_docs: list[NavDoc] = field(default_factory=list)


@dataclass
class NavCategory:
    name: str
    sources: list[NavSource] = field(default_factory=list)


# ── Site context builder ───────────────────────────────────────────────────────


def _dedup_source_slugs(sources: list[NavSource]) -> None:
    """Ensure NavSource slugs are unique by appending numeric suffixes.

    Two sources with names that slugify identically (e.g. "My Project" and
    "my-project" both → "my-project") would overwrite each other's output
    directory.  This mutates slug and index_url in-place to prevent that.
    """
    seen: dict[str, int] = {}
    for src in sources:
        base = src.slug
        if base in seen:
            seen[base] += 1
            old_slug = src.slug
            src.slug = f"{base}-{seen[base]}"
            src.index_url = f"{_slugify(src.category)}/{src.slug}/index.html"
            # Patch NavDoc URLs already built with the old slug so nav links
            # stay consistent with where _gen_doc_page will actually write files.
            for doc in src.docs:
                doc.url = doc.url.replace(f"/{old_slug}/", f"/{src.slug}/", 1)
            log.warning(
                "Source slug collision: '%s' → '%s' (renamed to avoid overwrite)",
                src.name,
                src.slug,
            )
        else:
            seen[base] = 0


def _dedup_doc_urls(docs: list[NavDoc]) -> None:
    """Ensure NavDoc URLs are unique within a source by appending suffixes.

    _path_slug is designed to be collision-resistant, but edge cases like
    long filenames that truncate to the same suffix could still collide.
    """
    seen: dict[str, int] = {}
    for doc in docs:
        url = doc.url
        if url in seen:
            seen[url] += 1
            # Replace .html suffix with -N.html
            stem = url.rsplit(".html", 1)[0]
            doc.url = f"{stem}-{seen[url]}.html"
            log.warning("Doc URL collision: '%s' renamed to '%s'", url, doc.url)
        else:
            seen[url] = 0


def _dedup_doc_path_slugs(
    nav_source: NavSource, docs: list[ParsedDoc]
) -> dict[str, str]:
    """Build a mapping of rel_path → deduplicated output path for docs.

    Returns a dict mapping each doc's rel_path to its final relative output
    path (e.g. ``"general/my-project/guide.html"``).  If two docs within
    the same source produce the same ``_path_slug``, a numeric suffix is
    appended to disambiguate.
    """
    cat_slug = _slugify(nav_source.category)
    src_slug = nav_source.slug
    prefix = f"{cat_slug}/{src_slug}/"

    result: dict[str, str] = {}
    seen: dict[str, int] = {}
    for doc in docs:
        slug = _path_slug(doc.rel_path)
        rel_path = f"{prefix}{slug}.html"
        if rel_path in seen:
            seen[rel_path] += 1
            slug = f"{slug}-{seen[rel_path]}"
            rel_path = f"{prefix}{slug}.html"
            log.warning(
                "Doc path collision: '%s' → '%s' for source '%s'",
                doc.rel_path,
                rel_path,
                nav_source.name,
            )
        else:
            seen[rel_path] = 0
        result[doc.rel_path] = rel_path
    return result


def _build_nav(
    config: dict,
    docs_by_source: dict[str, list[ParsedDoc]],
    sync_timestamp: Optional[str] = None,
) -> list[NavCategory]:
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

        readme_doc: Optional[NavDoc] = None
        primary_docs: list[NavDoc] = []
        additional_docs: list[NavDoc] = []

        for d in source_docs_sorted:
            nav_doc = NavDoc(
                title=d.title,
                url=f"{cat_slug}/{slug}/{_path_slug(d.rel_path)}.html",
                description=d.description,
            )
            if d.rel_path.lower() == "readme.md":
                readme_doc = nav_doc
            elif d.rel_path.startswith("docs/"):
                primary_docs.append(nav_doc)
            else:
                additional_docs.append(nav_doc)

        # README first, then docs/, then everything else — dedup across all
        nav_docs = ([readme_doc] if readme_doc else []) + primary_docs + additional_docs
        _dedup_doc_urls(nav_docs)

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
            last_synced=sync_timestamp or "",
            docs=nav_docs,
            readme_doc=readme_doc,
            primary_docs=primary_docs,
            additional_docs=additional_docs,
        )

        if cat_name not in categories:
            categories[cat_name] = NavCategory(name=cat_name)
        categories[cat_name].sources.append(nav_source)

    # Deduplicate source slugs across all categories
    all_sources = [s for c in categories.values() for s in c.sources]
    _dedup_source_slugs(all_sources)

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

    def __init__(
        self,
        config: dict,
        docs: list[ParsedDoc],
        sync_timestamp: Optional[str] = None,
    ) -> None:
        self._config = config
        self._all_docs = docs

        site_cfg = config.get("site", {})
        self._output_dir = Path(site_cfg.get("output_dir", "/tmp/docsync-out"))
        self._site_title = site_cfg.get("title", "DocSync Wiki")

        # Group docs by source name
        self._docs_by_source: dict[str, list[ParsedDoc]] = {}
        for doc in docs:
            self._docs_by_source.setdefault(doc.source_name, []).append(doc)

        self._nav = _build_nav(config, self._docs_by_source, sync_timestamp)
        self._env = _make_env()
        self._last_synced = sync_timestamp or datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )

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
        ctx.update(
            {
                "page_title": "Dashboard",
                "total_docs": total_docs,
                "total_sources": total_sources,
                "backup_statuses": bk_statuses,
            }
        )
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
            nav_src = next(
                (s for c in self._nav for s in c.sources if s.name == doc.source_name),
                None,
            )
            cat_slug = _slugify(nav_src.category if nav_src else "misc")
            src_slug = nav_src.slug if nav_src else _slugify(doc.source_name)
            updates.append(
                {
                    "title": doc.title,
                    "source_name": doc.source_name,
                    "rel_path": doc.rel_path,
                    "url": f"{cat_slug}/{src_slug}/{_path_slug(doc.rel_path)}.html",
                    "synced_at": self._last_synced,
                }
            )
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
        max_bytes = int(max_gb * 1024**3) if max_gb else 0
        pct_used = min(100, int(used_bytes / max_bytes * 100)) if max_bytes > 0 else 0

        # Alert banners
        alerts: list[dict] = []
        failed = [s for s in statuses if s["health"] == "err"]
        stale = [
            s for s in statuses if s["health"] == "warn" and s["snapshot_count"] > 0
        ]
        if failed:
            alerts.append(
                {
                    "level": "err",
                    "message": f"{len(failed)} source(s) failed last backup: "
                    + ", ".join(s["source_name"] for s in failed),
                }
            )
        if stale:
            alerts.append(
                {
                    "level": "warn",
                    "message": f"{len(stale)} source(s) have stale backups: "
                    + ", ".join(s["source_name"] for s in stale),
                }
            )
        if max_bytes and pct_used >= 80:
            alerts.append(
                {
                    "level": "warn",
                    "message": f"Storage at {pct_used}% of limit "
                    f"({human_size(used_bytes)} / {human_size(max_bytes)})",
                }
            )

        # Main backups dashboard
        ctx = self._base_ctx(root_path="", current_page="backups")
        ctx.update(
            {
                "page_title": "Backups",
                "backup_statuses": statuses,
                "backup_events": events,
                "storage_used_bytes": used_bytes,
                "storage_used_human": human_size(used_bytes),
                "storage_max_bytes": max_bytes,
                "storage_max_human": human_size(max_bytes) if max_bytes else "",
                "storage_pct": pct_used,
                "alerts": alerts,
            }
        )
        self._write("backups.html", self._render("backups.html", ctx))
        pages = 1

        # Per-source snapshot browser pages
        backup_sources = [
            src
            for src in self._config.get("sources", [])
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
            ctx.update(
                {
                    "page_title": f"{name} — Snapshots",
                    "source_name": name,
                    "source_slug": slug,
                    "source_type": src.get("type", "local"),
                    "source_path": src.get("path", src.get("host", "")),
                    "snapshots": snaps,
                    "status": src_status,
                }
            )
            self._write(f"backups/{slug}.html", self._render("backup_source.html", ctx))
            pages += 1

        return pages

    def _gen_project_page(
        self,
        nav_source: NavSource,
        source_docs: list[ParsedDoc],
        doc_path_map: Optional[dict[str, str]] = None,
    ) -> None:
        cat_slug = _slugify(nav_source.category)
        src_slug = nav_source.slug
        root_path = "../../"

        docs_sorted = sorted(source_docs, key=lambda d: (d.order, d.title))
        doc_list = [
            {
                "title": d.title,
                "description": d.description,
                "url": (doc_path_map or {}).get(
                    d.rel_path,
                    f"{cat_slug}/{src_slug}/{_path_slug(d.rel_path)}.html",
                ),
                "tags": d.tags,
                "rel_path": d.rel_path,
            }
            for d in docs_sorted
        ]

        ctx = self._base_ctx(
            root_path=root_path,
            current_source=nav_source.name,
        )
        ctx.update(
            {
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
            }
        )
        self._write(
            f"{cat_slug}/{src_slug}/index.html",
            self._render("project.html", ctx),
        )

    @staticmethod
    def _extract_prose_from_html(html: str) -> str:
        """Extract the prose body from a previously rendered doc page.

        Used when a nav-only doc (html_body=="") needs its output file
        regenerated (e.g. to refresh prev/next links) without losing prose.
        """
        m = re.search(
            r'<div class="prose">\s*(.*?)\s*<!-- Prev/Next',
            html,
            re.DOTALL,
        )
        return m.group(1).strip() if m else ""

    def _gen_doc_page(
        self,
        doc: ParsedDoc,
        nav_source: NavSource,
        prev_doc: Optional[ParsedDoc],
        next_doc: Optional[ParsedDoc],
        doc_path_map: Optional[dict[str, str]] = None,
    ) -> str:
        """Generate one doc page; returns the relative output path.

        For nav-only docs (html_body == ""), restore prose from the existing
        output file so incremental syncs preserve content while refreshing
        navigation links (prev/next, breadcrumbs).
        """
        cat_slug = _slugify(nav_source.category)
        src_slug = nav_source.slug
        default_path = f"{cat_slug}/{src_slug}/{_path_slug(doc.rel_path)}.html"
        rel_out = (doc_path_map or {}).get(doc.rel_path, default_path)
        root_path = "../../"

        # Nav-only sentinel: restore prose from disk so prev/next links refresh
        # without wiping existing content.
        if not doc.html_body:
            out_path = self._output_dir / rel_out
            if out_path.exists():
                try:
                    existing = out_path.read_text(encoding="utf-8", errors="replace")
                    restored = self._extract_prose_from_html(existing)
                    if restored:
                        doc = ParsedDoc(
                            source_name=doc.source_name,
                            rel_path=doc.rel_path,
                            abs_path=doc.abs_path,
                            title=doc.title,
                            description=doc.description,
                            tags=doc.tags,
                            order=doc.order,
                            html_body=restored,
                            toc=doc.toc,
                            raw_front_matter=doc.raw_front_matter,
                        )
                except OSError:
                    pass  # can't read existing file — generate with empty prose

        def nav_entry(d: Optional[ParsedDoc]) -> Optional[dict]:
            if d is None:
                return None
            default = f"{cat_slug}/{src_slug}/{_path_slug(d.rel_path)}.html"
            return {
                "title": d.title,
                "url": (doc_path_map or {}).get(d.rel_path, default),
            }

        ctx = self._base_ctx(
            root_path=root_path,
            current_source=nav_source.name,
            current_doc_url=rel_out,
        )
        ctx.update(
            {
                "page_title": doc.title,
                "doc": doc,
                "source": {
                    "name": nav_source.name,
                    "category": nav_source.category,
                    "index_url": nav_source.index_url,
                },
                "prev_doc": nav_entry(prev_doc),
                "next_doc": nav_entry(next_doc),
            }
        )
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
                source_docs_sorted = sorted(
                    source_docs, key=lambda d: (d.order, d.title)
                )

                # Deduplicate doc output paths within this source to prevent
                # file overwrites from _path_slug collisions (e.g. truncation).
                doc_path_map = _dedup_doc_path_slugs(nav_source, source_docs_sorted)

                self._gen_project_page(nav_source, source_docs_sorted, doc_path_map)
                pages += 1

                for i, doc in enumerate(source_docs_sorted):
                    prev_d = source_docs_sorted[i - 1] if i > 0 else None
                    next_d = (
                        source_docs_sorted[i + 1]
                        if i < len(source_docs_sorted) - 1
                        else None
                    )
                    self._gen_doc_page(doc, nav_source, prev_d, next_d, doc_path_map)
                    pages += 1

        log.info("Site generated: %d pages → %s", pages, self._output_dir)
        return pages


# ── Public API ─────────────────────────────────────────────────────────────────


def generate_site(
    config: dict,
    docs: list[ParsedDoc],
    recent_docs: Optional[list] = None,
    sync_timestamp: Optional[str] = None,
) -> int:
    """Generate the static site. Returns page count.

    Args:
        sync_timestamp: Optional timestamp string for "last synced" display.
            If None, uses current time.
    """
    gen = SiteGenerator(config, docs, sync_timestamp=sync_timestamp)
    return gen.generate(recent_docs=recent_docs)
