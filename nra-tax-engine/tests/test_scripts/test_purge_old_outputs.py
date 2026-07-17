"""Tests for scripts/purge_old_outputs.py — the outputs/ + audit-dir retention sweep.

Covers: files older than the cutoff get deleted, files newer than the cutoff
are left alone, --dry-run deletes nothing while still reporting what it would
delete, and the path-containment safety check (mirrors the packet-download
path-traversal guard in src/api/main.py) refuses to touch anything outside
the configured root even when handed a path engineered to escape it.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.purge_old_outputs import (
    is_contained,
    main,
    purge_dir,
    safe_delete,
)


def _age_file(path: Path, days_old: float) -> None:
    """Set both atime and mtime of ``path`` to ``days_old`` days in the past."""
    ts = time.time() - days_old * 86400
    os.utime(path, (ts, ts))


@pytest.fixture
def outputs_root(tmp_path: Path) -> Path:
    root = tmp_path / "outputs"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# Core retention behavior
# ---------------------------------------------------------------------------


def test_files_older_than_cutoff_are_deleted(outputs_root: Path):
    stale = outputs_root / "filing_123" / "1040-NR.pdf"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"%PDF-1.4 fake old packet")
    _age_file(stale, days_old=45)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    summary = purge_dir(outputs_root, cutoff, dry_run=False, verbose=False)

    assert summary.deleted_count == 1
    assert summary.freed_bytes == len(b"%PDF-1.4 fake old packet")
    assert not stale.exists()


def test_files_newer_than_cutoff_are_kept(outputs_root: Path):
    fresh = outputs_root / "filing_456" / "1040-NR.pdf"
    fresh.parent.mkdir(parents=True)
    fresh.write_bytes(b"%PDF-1.4 fake fresh packet")
    _age_file(fresh, days_old=5)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    summary = purge_dir(outputs_root, cutoff, dry_run=False, verbose=False)

    assert summary.deleted_count == 0
    assert fresh.exists()


def test_mixed_ages_only_old_ones_removed(outputs_root: Path):
    old = outputs_root / "old.pdf"
    new = outputs_root / "new.pdf"
    old.write_bytes(b"old-bytes")
    new.write_bytes(b"new-bytes-longer")
    _age_file(old, days_old=60)
    _age_file(new, days_old=1)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    summary = purge_dir(outputs_root, cutoff, dry_run=False, verbose=False)

    assert summary.deleted_count == 1
    assert not old.exists()
    assert new.exists()


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


def test_dry_run_deletes_nothing_but_reports(outputs_root: Path, capsys):
    stale = outputs_root / "stale.pdf"
    stale.write_bytes(b"stale-packet-bytes")
    _age_file(stale, days_old=90)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    summary = purge_dir(outputs_root, cutoff, dry_run=True)

    # Still on disk -- dry-run must never delete.
    assert stale.exists()
    # But it was correctly identified as a deletion candidate.
    assert summary.deleted_count == 1
    assert summary.freed_bytes == len(b"stale-packet-bytes")
    assert stale.resolve() in [p.resolve() for p in summary.deleted_paths]

    out = capsys.readouterr().out
    assert "dry-run" in out.lower()


def test_cli_dry_run_end_to_end(outputs_root: Path, capsys, monkeypatch):
    stale = outputs_root / "stale.pdf"
    stale.write_bytes(b"x" * 100)
    _age_file(stale, days_old=90)
    monkeypatch.delenv("QUADTAX_AUDIT_DIR", raising=False)

    rc = main(["--days", "30", "--dry-run", "--outputs-dir", str(outputs_root)])

    assert rc == 0
    assert stale.exists()
    out = capsys.readouterr().out
    assert "would delete 1 file" in out.lower()


def test_cli_real_run_deletes_and_summarizes(outputs_root: Path, capsys, monkeypatch):
    stale = outputs_root / "stale.pdf"
    fresh = outputs_root / "fresh.pdf"
    stale.write_bytes(b"x" * 50)
    fresh.write_bytes(b"y" * 50)
    _age_file(stale, days_old=90)
    _age_file(fresh, days_old=1)
    monkeypatch.delenv("QUADTAX_AUDIT_DIR", raising=False)

    rc = main(["--days", "30", "--outputs-dir", str(outputs_root)])

    assert rc == 0
    assert not stale.exists()
    assert fresh.exists()
    out = capsys.readouterr().out
    assert "deleted 1 file" in out.lower()
    assert "50" in out or "B" in out  # freed-bytes summary present in some unit


def test_cli_also_purges_audit_dir_when_env_set(tmp_path: Path, outputs_root: Path, monkeypatch):
    audit_root = tmp_path / "audit"
    stale_audit = audit_root / "filing_789" / "audit.jsonl"
    stale_audit.parent.mkdir(parents=True)
    stale_audit.write_text('{"layer": "L1"}\n')
    _age_file(stale_audit, days_old=99)
    monkeypatch.setenv("QUADTAX_AUDIT_DIR", str(audit_root))

    rc = main(["--days", "30", "--outputs-dir", str(outputs_root)])

    assert rc == 0
    assert not stale_audit.exists()


# ---------------------------------------------------------------------------
# Path-containment safety check
# ---------------------------------------------------------------------------


def test_is_contained_true_for_descendant(outputs_root: Path):
    child = outputs_root / "sub" / "file.pdf"
    child.parent.mkdir(parents=True)
    child.write_text("x")
    assert is_contained(child, outputs_root) is True


def test_is_contained_false_for_sibling_prefix_directory(tmp_path: Path):
    """outputs_evil/ must not be treated as contained in outputs/ (string-prefix trap)."""
    root = tmp_path / "outputs"
    root.mkdir()
    evil = tmp_path / "outputs_evil" / "file.pdf"
    evil.parent.mkdir(parents=True)
    evil.write_text("x")
    assert is_contained(evil, root) is False


def test_is_contained_false_for_parent_traversal(tmp_path: Path):
    root = tmp_path / "outputs"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("do not delete me")
    traversal_path = root / ".." / "secret.txt"
    assert is_contained(traversal_path, root) is False


def test_safe_delete_refuses_path_outside_root(tmp_path: Path):
    root = tmp_path / "outputs"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "important.pdf"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"do not delete me")

    result = safe_delete(outside, root)

    assert result is False
    assert outside.exists()


def test_safe_delete_refuses_sibling_prefix_directory(tmp_path: Path):
    root = tmp_path / "outputs"
    root.mkdir()
    evil = tmp_path / "outputs_evil" / "file.pdf"
    evil.parent.mkdir(parents=True)
    evil.write_bytes(b"do not delete me")

    result = safe_delete(evil, root)

    assert result is False
    assert evil.exists()


def test_safe_delete_allows_path_inside_root(outputs_root: Path):
    target = outputs_root / "file.pdf"
    target.write_bytes(b"safe to delete")

    result = safe_delete(target, outputs_root)

    assert result is True
    assert not target.exists()


def test_purge_dir_never_follows_symlink_out_of_root_to_delete_target(
    tmp_path: Path, outputs_root: Path
):
    """A symlink inside outputs/ pointing outside must not cause the external
    target to be deleted, even though the (stale) symlink entry itself is a
    legitimate deletion candidate."""
    external_target = tmp_path / "external_secret.pdf"
    external_target.write_bytes(b"outside the root, must survive")

    link = outputs_root / "link_to_external.pdf"
    link.symlink_to(external_target)
    _age_file(link, days_old=90)
    # os.utime on a symlink by default follows the link on many platforms;
    # ensure the external target's own mtime doesn't matter here -- what
    # matters is that it still exists afterward regardless of its age.

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    purge_dir(outputs_root, cutoff, dry_run=False, verbose=False)

    # The external file must never be touched, no matter what happened to
    # the symlink that referenced it.
    assert external_target.exists()
    assert external_target.read_bytes() == b"outside the root, must survive"


def test_purge_dir_reports_but_does_not_error_on_nonexistent_root(tmp_path: Path):
    missing = tmp_path / "does_not_exist"
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    summary = purge_dir(missing, cutoff, dry_run=False, verbose=False)

    assert summary.deleted_count == 0
    assert summary.freed_bytes == 0
