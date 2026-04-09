"""Sync orchestration — collect, parse, update manifest, and generate site."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .collector import CollectResult, collect_all
from .config import load_and_validate, ConfigError
from .generator import generate_site
from .manifest import Manifest
from .parser import ParsedDoc, parse_files

log = logging.getLogger(__name__)


@dataclass
class SyncStats:
    sources_processed: int = 0
    sources_skipped: int = 0
    files_collected: int = 0
    files_changed: int = 0
    files_parsed: int = 0
    pages_generated: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.errors


def run_sync(
    config: dict,
    manifest: Manifest,
    source_name: Optional[str] = None,
) -> tuple[SyncStats, list[ParsedDoc]]:
    """Run a full doc sync for all (or one named) local source(s).

    Returns (stats, list of ParsedDoc for changed files).
    The manifest is updated and saved on success.
    """
    t0 = time.monotonic()
    stats = SyncStats()
    all_docs: list[ParsedDoc] = []

    # Collect
    try:
        results: list[CollectResult] = collect_all(config, manifest, source_name)
    except ValueError as exc:
        stats.errors.append(str(exc))
        stats.duration_seconds = time.monotonic() - t0
        return stats, []

    for result in results:
        stats.sources_processed += 1

        if result.errors:
            for err in result.errors:
                log.error("[%s] %s", result.source_name, err)
                stats.errors.append(f"[{result.source_name}] {err}")
            stats.sources_skipped += 1
            continue

        stats.files_collected += len(result.files)
        stats.files_changed += len(result.changed_files)

        # Parse only changed files (unchanged files are already rendered)
        docs = parse_files(result.files, changed_only=True)
        stats.files_parsed += len(docs)
        all_docs.extend(docs)

        # Update manifest — store doc metadata for changed files so the nav
        # can be rebuilt from the manifest without re-reading files next run.
        parsed_by_key = {f"{d.source_name}/{d.rel_path}": d for d in docs}
        for f in result.files:
            key = f"{f.source_name}/{f.rel_path}"
            parsed = parsed_by_key.get(key)
            if parsed:
                manifest.update(
                    f.source_name,
                    f.rel_path,
                    f.abs_path,
                    title=parsed.title,
                    description=parsed.description,
                    tags=parsed.tags,
                    order=parsed.order,
                )
            else:
                manifest.update(f.source_name, f.rel_path, f.abs_path)

    manifest.save()

    # Generate static site — nav from manifest metadata (no re-parsing),
    # HTML regenerated only for changed docs.
    sync_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    from .parser import load_nav_docs_from_manifest

    nav_docs = load_nav_docs_from_manifest(config, manifest._data)

    # Merge: changed docs (with full HTML) override nav-only metadata docs.
    changed_by_key = {f"{d.source_name}/{d.rel_path}": d for d in all_docs}
    merged_docs = [
        changed_by_key.get(f"{d.source_name}/{d.rel_path}", d) for d in nav_docs
    ]

    if merged_docs or not stats.errors:
        try:
            stats.pages_generated = generate_site(
                config, merged_docs, recent_docs=all_docs, sync_timestamp=sync_ts
            )
        except Exception as exc:
            log.error("Site generation failed: %s", exc)
            stats.errors.append(f"Site generation failed: {exc}")

    stats.duration_seconds = time.monotonic() - t0
    return stats, all_docs
