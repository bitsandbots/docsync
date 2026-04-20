"""Markdown parser with front matter extraction and heading-based TOC generation.

Uses markdown-it-py for rendering and PyYAML for front matter.
"""

import html
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token

log = logging.getLogger(__name__)

# ── Markdown renderer ─────────────────────────────────────────────────────────

_md = MarkdownIt("commonmark", {"html": False})  # disable raw HTML for XSS safety

# ── Data structures ───────────────────────────────────────────────────────────

_FRONT_MATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_SLUG_STRIP_RE = re.compile(r"[^\w\s-]")
_SLUG_COLLAPSE_RE = re.compile(r"[\s-]+")


@dataclass
class TocEntry:
    level: int  # 1-6
    text: str  # plain-text heading
    slug: str  # URL fragment


@dataclass
class ParsedDoc:
    """Result of parsing a single markdown file."""

    source_name: str
    rel_path: str
    abs_path: Path

    # Front matter fields (with defaults)
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    order: int = 9999

    # Parsed content
    html_body: str = ""
    toc: list[TocEntry] = field(default_factory=list)
    raw_front_matter: dict[str, Any] = field(default_factory=dict)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """Convert a heading string to a URL-safe slug."""
    text = text.lower().strip()
    text = _SLUG_STRIP_RE.sub("", text)
    text = _SLUG_COLLAPSE_RE.sub("-", text)
    return text.strip("-")


def _extract_front_matter(source: str) -> tuple[dict[str, Any], str]:
    """Strip YAML front matter from the top of *source* and return (meta, body)."""
    m = _FRONT_MATTER_RE.match(source)
    if not m:
        return {}, source
    try:
        meta = yaml.safe_load(m.group(1)) or {}
        if not isinstance(meta, dict):
            meta = {}
    except yaml.YAMLError:
        meta = {}
    body = source[m.end() :]
    return meta, body


def _build_toc(tokens: list[Token]) -> list[TocEntry]:
    """Extract headings from markdown-it token stream."""
    toc: list[TocEntry] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])  # h1 -> 1, h2 -> 2 …
            # The next token is inline content
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                raw = tokens[i + 1].content
                # Strip any inline markup (bold, code, etc.) for plain text
                plain = re.sub(r"`[^`]*`|\*+|_+", "", raw).strip()
                toc.append(TocEntry(level=level, text=plain, slug=_slugify(plain)))
        i += 1
    return toc


def _inject_heading_ids(rendered_html: str, toc: list[TocEntry]) -> str:
    """Add id= attributes to <h1>–<h6> tags so TOC anchor links work."""
    toc_iter = iter(toc)
    entry: Optional[TocEntry] = None

    def replacer(m: re.Match) -> str:
        nonlocal entry
        try:
            entry = next(toc_iter)
        except StopIteration:
            return m.group(0)
        tag = m.group(1)
        return f'<{tag} id="{html.escape(entry.slug)}">'

    return re.sub(r"<(h[1-6])>", replacer, rendered_html)


# ── Public API ────────────────────────────────────────────────────────────────


def parse_file(abs_path: Path, source_name: str, rel_path: str) -> Optional[ParsedDoc]:
    """Parse a single markdown file and return a ParsedDoc.

    Returns None if the file cannot be read.
    """
    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        log.error("Cannot read %s: %s", abs_path, exc)
        return None

    meta, body = _extract_front_matter(source)

    # Render via markdown-it; get token stream for TOC extraction
    tokens = _md.parse(body)
    toc = _build_toc(tokens)
    rendered = _md.renderer.render(tokens, _md.options, {})
    rendered = _inject_heading_ids(rendered, toc)

    # Derive title: front matter > first h1 in TOC > filename stem
    title = meta.get("title", "")
    if not title:
        for entry in toc:
            if entry.level == 1:
                title = entry.text
                break
    if not title:
        title = Path(rel_path).stem.replace("-", " ").replace("_", " ").title()

    return ParsedDoc(
        source_name=source_name,
        rel_path=rel_path,
        abs_path=abs_path,
        title=title,
        description=meta.get("description", ""),
        tags=meta.get("tags", []),
        order=meta.get("order", 9999),
        html_body=rendered,
        toc=toc,
        raw_front_matter=meta,
    )


def parse_files(
    files: list,  # list[CollectedFile] — avoid circular import
    changed_only: bool = False,
) -> list[ParsedDoc]:
    """Parse a list of CollectedFile objects.

    If *changed_only* is True, only re-parse files that changed.
    """
    docs: list[ParsedDoc] = []
    for f in files:
        if changed_only and not f.changed:
            continue
        doc = parse_file(f.abs_path, f.source_name, f.rel_path)
        if doc:
            docs.append(doc)
    return docs


def load_nav_docs_from_manifest(
    config: dict,
    manifest_data: dict[str, dict],
) -> list[ParsedDoc]:
    """Build lightweight ParsedDoc objects from metadata cached in the manifest.

    No disk I/O or markdown rendering — uses title/description/order/tags stored
    by previous parse runs.  Falls back to a filename-derived title for older
    entries that predate metadata storage.

    Returns docs with ``html_body=""`` — the generator treats these as
    nav-only: it reads the existing output file to restore any previously
    rendered prose before re-rendering, so prev/next links refresh without
    losing content.
    """
    sources = {s["name"]: s for s in config.get("sources", [])}
    docs: list[ParsedDoc] = []

    for key, entry in manifest_data.items():
        if "/" not in key:
            continue
        source_name = key.split("/", 1)[0]
        rel_path = key[len(source_name) + 1 :]

        if source_name not in sources:
            continue

        title = (
            entry.get("title")
            or Path(rel_path).stem.replace("-", " ").replace("_", " ").title()
        )

        docs.append(
            ParsedDoc(
                source_name=source_name,
                rel_path=rel_path,
                abs_path=Path(),  # not needed for nav-only docs
                title=title,
                description=entry.get("description", ""),
                tags=entry.get("tags", []),
                order=entry.get("order", 9999),
                html_body="",  # sentinel: nav-only, no HTML regeneration
            )
        )

    return docs


# ── Code documentation extraction ────────────────────────────────────────────

_CODE_DOC_PATTERNS: dict[str, tuple[str, str]] = {
    # language: (glob_pattern, regex_to_extract)
    "python": ("**/*.py", r'"""(.*?)"""'),
    "php": ("**/*.php", r"/\*\*(.*?)\*/"),
    "cpp": ("**/*.{cpp,h,ino}", r"///(.*)$"),
}


def extract_code_docs(
    source_root: Path,
    code_docs_config: dict,
) -> list[ParsedDoc]:
    """Extract doc comments from source code per the code_docs config.

    Returns ParsedDoc instances with html_body containing extracted comments.
    """
    if not code_docs_config.get("enabled"):
        return []

    docs: list[ParsedDoc] = []
    languages = code_docs_config.get("languages", {})

    for lang, lang_cfg in languages.items():
        pattern = lang_cfg.get("pattern", _CODE_DOC_PATTERNS.get(lang, ("", ""))[1])

        if not pattern:
            continue

        for src_file in source_root.rglob("*"):
            if not src_file.is_file():
                continue
            # Simple suffix check
            if lang == "python" and src_file.suffix != ".py":
                continue
            elif lang == "php" and src_file.suffix != ".php":
                continue
            elif lang == "cpp" and src_file.suffix not in (".cpp", ".h", ".ino"):
                continue

            try:
                text = src_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            flags = re.DOTALL if lang != "cpp" else 0
            matches = re.findall(pattern, text, flags)
            if not matches:
                continue

            combined = "\n\n".join(m.strip() for m in matches)
            # Render as markdown
            tokens = _md.parse(combined)
            rendered = _md.renderer.render(tokens, _md.options, {})
            rel = src_file.relative_to(source_root).as_posix()
            title = src_file.stem.replace("_", " ").title() + f" ({lang})"

            docs.append(
                ParsedDoc(
                    source_name=source_root.name,
                    rel_path=rel,
                    abs_path=src_file,
                    title=title,
                    description=f"Code documentation extracted from {rel}",
                    html_body=rendered,
                )
            )

    return docs
