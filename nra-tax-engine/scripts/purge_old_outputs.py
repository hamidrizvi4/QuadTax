#!/usr/bin/env python3
"""Delete generated filing packets (and stale audit-trail files) older than N days.

QuadTax's assembly layer (see ``src/assembly/form_populator.py``,
``FormPopulator.__init__``'s ``outputs_dir`` handling) writes every generated
filing packet -- 1040-NR PDFs, Schedule OI, FICA 843 forms, and so on, all of
which carry real SSN/ITIN and wage data -- to ``outputs/`` by default. Nothing
in the engine ever purges those files, so PII-bearing packets accumulate on
disk indefinitely. That is a real PII-exposure risk over time, independent of
the fact that ``outputs/`` is (correctly) gitignored -- this is about actual
disk cleanup, not git exposure.

Separately, when the ``QUADTAX_AUDIT_DIR`` environment variable is set (see
``src/orchestrator/audit.py``), every state mutation is appended as one line
of JSONL to ``<QUADTAX_AUDIT_DIR>/<filing_id>/audit.jsonl``. Those files are
PII-adjacent (hashed identifiers plus redacted-but-still-sensitive previews)
and accumulate forever too, so this script sweeps that tree as well whenever
the env var is present.

This script is a standalone, one-shot retention sweep: it deletes files under
those trees whose *modification time* (mtime) is older than ``--days`` days
(30 by default). It does **not** install itself anywhere and this repository
has no cron/scheduler infrastructure -- to run it on a schedule in production,
wire it into whatever your platform offers, e.g.:

    # crontab -e  (run daily at 03:15, keep 30 days)
    15 3 * * * cd /path/to/nra-tax-engine && \\
        /usr/bin/python3 scripts/purge_old_outputs.py --days 30 \\
        >> /var/log/quadtax-purge.log 2>&1

    # systemd timer unit (paired with a .service running the command above),
    # a Kubernetes CronJob, a GitHub Actions scheduled workflow ("on: schedule"),
    # or a cloud provider's scheduled-job feature (e.g. AWS EventBridge Scheduler,
    # GCP Cloud Scheduler) all work the same way -- invoke
    # `python3 scripts/purge_old_outputs.py --days N` on whatever cadence your
    # retention policy requires.

Usage::

    python -m scripts.purge_old_outputs                    # purge files older than 30 days
    python -m scripts.purge_old_outputs --days 7            # purge files older than 7 days
    python -m scripts.purge_old_outputs --days 7 --dry-run  # preview only, deletes nothing

Safety
------
This script will only ever delete a file whose *resolved* real path
(``os.path.realpath``) is contained within the resolved real path of its
configured root (``outputs/`` -- or ``--outputs-dir``, plus
``QUADTAX_AUDIT_DIR`` when set) -- the same containment check used by the
packet-download endpoint's path-traversal guard in ``src/api/main.py``
(``download_packet``): resolve both sides with ``os.path.realpath`` and
compare via ``os.path.commonpath`` rather than a naive ``str.startswith``
check, which would wrongly admit a sibling directory such as
``outputs_evil/`` (the *string* "outputs_evil" starts with "outputs" even
though it is not a descendant of the outputs directory on the filesystem).
Every candidate file is re-validated against this guard immediately before
deletion, so nothing outside the configured roots is ever touched, even if a
symlink or a crafted path tries to trick it.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional

DEFAULT_OUTPUTS_DIR = "outputs"
_AUDIT_DIR_ENV = "QUADTAX_AUDIT_DIR"


@dataclass
class PurgeSummary:
    """Tally of what was (or, under ``--dry-run``, would be) removed from one root."""

    root: Path
    deleted_count: int = 0
    freed_bytes: int = 0
    skipped_unsafe: int = 0
    deleted_paths: List[Path] = field(default_factory=list)


def is_contained(path: Path, root: Path) -> bool:
    """Return True iff the resolved real path of ``path`` is inside ``root``.

    Mirrors the containment check in ``download_packet`` (``src/api/main.py``):
    resolve both sides with ``os.path.realpath`` and compare via
    ``os.path.commonpath`` rather than a string-prefix test, so a symlink or a
    sibling directory like ``outputs_evil/`` can never be mistaken for a
    descendant of ``root``.
    """
    path_abs = os.path.realpath(str(path))
    root_abs = os.path.realpath(str(root))
    try:
        return os.path.commonpath([path_abs, root_abs]) == root_abs
    except ValueError:
        # Raised when the paths are on different drives (Windows) -- never contained.
        return False


def iter_files(root: Path) -> Iterable[Path]:
    """Yield every regular file under ``root`` (recursively). ``root`` need not exist."""
    if not root.exists():
        return
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            yield Path(dirpath) / name


def safe_delete(path: Path, root: Path) -> bool:
    """Delete ``path`` iff its real path is contained within ``root``'s real path.

    Returns True if the file was deleted, False if it was refused (outside
    ``root``) or the delete failed. Exposed as a small standalone primitive,
    in addition to the bulk :func:`purge_dir` sweep below, so the containment
    guard can be exercised directly against paths engineered to escape
    ``root`` (e.g. from tests).
    """
    if not is_contained(path, root):
        return False
    try:
        Path(path).unlink()
        return True
    except OSError:
        return False


def purge_dir(
    root: Path,
    cutoff: datetime,
    *,
    dry_run: bool,
    verbose: bool = True,
) -> PurgeSummary:
    """Delete (or, if ``dry_run``, just report) files under ``root`` older than ``cutoff``.

    "Older than ``cutoff``" is determined by file mtime. Every candidate is
    re-validated with :func:`is_contained` immediately before deletion, so
    nothing outside ``root`` is ever touched even if ``root`` itself was
    passed in with a trailing symlink or a ``..`` segment.
    """
    root_abs = Path(os.path.realpath(str(root)))
    summary = PurgeSummary(root=root_abs)
    cutoff_ts = cutoff.timestamp()

    for file_path in iter_files(root_abs):
        if not is_contained(file_path, root_abs):
            # Should be unreachable given os.walk(root_abs), but keep the
            # guard so the safety property holds even under future refactors.
            summary.skipped_unsafe += 1
            continue
        try:
            stat = file_path.stat()
        except OSError:
            continue
        if stat.st_mtime >= cutoff_ts:
            continue

        if dry_run:
            if verbose:
                print(f"[dry-run] would delete {file_path} ({stat.st_size} bytes)")
            summary.deleted_count += 1
            summary.freed_bytes += stat.st_size
            summary.deleted_paths.append(file_path)
            continue

        if safe_delete(file_path, root_abs):
            if verbose:
                print(f"deleted {file_path} ({stat.st_size} bytes)")
            summary.deleted_count += 1
            summary.freed_bytes += stat.st_size
            summary.deleted_paths.append(file_path)
        else:
            print(f"warning: failed to delete {file_path}", file=sys.stderr)

    return summary


def _human_bytes(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)}B" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"  # pragma: no cover - unreachable in practice


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="purge_old_outputs.py",
        description=(
            "Delete generated filing-packet files under outputs/ (and, if "
            "QUADTAX_AUDIT_DIR is set, stale audit-trail JSONL files under it) "
            "whose mtime is older than --days days. See the module docstring "
            "(python -m pydoc scripts.purge_old_outputs) for how to schedule "
            "this in production -- there is no scheduler wired up in this repo."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Delete files whose mtime is older than this many days (default: 30).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List what would be deleted without deleting anything (default: False).",
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUTS_DIR),
        help="Root directory of generated filing packets (default: outputs/).",
    )
    args = parser.parse_args(argv)

    if args.days < 0:
        parser.error("--days must be >= 0")

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    roots: List[Path] = [args.outputs_dir]
    audit_dir = os.environ.get(_AUDIT_DIR_ENV)
    if audit_dir:
        roots.append(Path(audit_dir))

    total_count = 0
    total_bytes = 0
    for root in roots:
        summary = purge_dir(root, cutoff, dry_run=args.dry_run)
        total_count += summary.deleted_count
        total_bytes += summary.freed_bytes
        if summary.skipped_unsafe:
            print(
                f"warning: skipped {summary.skipped_unsafe} unsafe path(s) under "
                f"{summary.root} (would have escaped the configured root)",
                file=sys.stderr,
            )

    if args.dry_run:
        print(
            f"[dry-run] would delete {total_count} file(s), "
            f"freeing {_human_bytes(total_bytes)}. Re-run without --dry-run to "
            "actually delete."
        )
    else:
        print(f"Summary: deleted {total_count} file(s), freed {_human_bytes(total_bytes)}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
