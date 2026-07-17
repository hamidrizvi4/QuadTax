"""Test POST /api/v1/erasure -- the GDPR Art. 17 right-to-erasure endpoint.

This engine has no user database: the two things it persists are per-form
output files (named "<name_stem>_<Form-Name>.pdf" / ".fieldmap.json" under
output_dir) and an optional per-filing_id audit-trail JSONL under
QUADTAX_AUDIT_DIR. These tests exercise deletion of both, the CORS-friendly
protection via require_api_key, path-safety on name_stem, idempotency, and
the documented limitation that packet_*.pdf files are not name-stem scoped.
"""

import json

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-key-not-a-secret"}


def test_erasure_requires_api_key():
    r = client.post("/api/v1/erasure", json={"name_stem": "Wei_Chen"})
    assert r.status_code == 401


def test_erasure_rejects_unsafe_name_stem():
    for bad in ["../../etc", "a/b", "a b", ""]:
        r = client.post(
            "/api/v1/erasure",
            json={"name_stem": bad},
            headers=AUTH,
        )
        assert r.status_code in (400, 422), bad


def test_erasure_deletes_matching_per_form_outputs(tmp_path):
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    mine_pdf = out_dir / "Wei_Chen_1040-NR.pdf"
    mine_pdf.write_text("pdf-bytes")
    mine_json = out_dir / "Wei_Chen_Schedule-OI.fieldmap.json"
    mine_json.write_text("{}")
    other_pdf = out_dir / "Amara_Diallo_1040-NR.pdf"
    other_pdf.write_text("someone else's return")

    r = client.post(
        "/api/v1/erasure",
        json={"name_stem": "Wei_Chen", "output_dir": str(out_dir)},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "erased"
    assert str(mine_pdf) in body["deleted_files"]
    assert str(mine_json) in body["deleted_files"]
    assert not mine_pdf.exists()
    assert not mine_json.exists()
    # A different filer's file in the same directory must be untouched.
    assert other_pdf.exists()


def test_erasure_is_idempotent_when_nothing_matches(tmp_path):
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    r = client.post(
        "/api/v1/erasure",
        json={"name_stem": "Nobody_Here", "output_dir": str(out_dir)},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["deleted_files"] == []


def test_erasure_missing_output_dir_is_not_an_error(tmp_path):
    missing = tmp_path / "does-not-exist"
    r = client.post(
        "/api/v1/erasure",
        json={"name_stem": "Wei_Chen", "output_dir": str(missing)},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["deleted_files"] == []
    assert any("does not exist" in w for w in r.json()["warnings"])


def test_erasure_leaves_shared_packets_by_default_and_warns(tmp_path):
    """packet_federal.pdf etc. are written by MailingPackager directly into
    output_dir with no name-stem prefix, so they cannot be safely
    attributed to one filer unless the caller explicitly opts in."""
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    packet = out_dir / "packet_federal.pdf"
    packet.write_text("merged packet")

    r = client.post(
        "/api/v1/erasure",
        json={"name_stem": "Wei_Chen", "output_dir": str(out_dir)},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert packet.exists()
    assert any("not name-stem scoped" in w for w in r.json()["warnings"])


def test_erasure_deletes_shared_packets_when_explicitly_requested(tmp_path):
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    packet = out_dir / "packet_federal.pdf"
    packet.write_text("merged packet")

    r = client.post(
        "/api/v1/erasure",
        json={
            "name_stem": "Wei_Chen",
            "output_dir": str(out_dir),
            "delete_shared_packets": True,
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    assert not packet.exists()
    assert str(packet) in r.json()["deleted_files"]


def test_erasure_deletes_audit_trail_when_filing_id_and_audit_dir_set(tmp_path, monkeypatch):
    audit_root = tmp_path / "audit"
    monkeypatch.setenv("QUADTAX_AUDIT_DIR", str(audit_root))

    filing_dir = audit_root / "fixture-001"
    filing_dir.mkdir(parents=True)
    audit_file = filing_dir / "audit.jsonl"
    audit_file.write_text(json.dumps({"layer": "L1"}) + "\n")

    out_dir = tmp_path / "outputs"
    out_dir.mkdir()

    r = client.post(
        "/api/v1/erasure",
        json={
            "name_stem": "Wei_Chen",
            "output_dir": str(out_dir),
            "filing_id": "fixture-001",
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_audit_path"] == str(audit_file)
    assert not audit_file.exists()


def test_erasure_warns_when_no_filing_id_supplied(tmp_path):
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    r = client.post(
        "/api/v1/erasure",
        json={"name_stem": "Wei_Chen", "output_dir": str(out_dir)},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert any("filing_id" in w for w in r.json()["warnings"])


def test_erasure_warns_when_audit_dir_not_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("QUADTAX_AUDIT_DIR", raising=False)
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    r = client.post(
        "/api/v1/erasure",
        json={
            "name_stem": "Wei_Chen",
            "output_dir": str(out_dir),
            "filing_id": "fixture-001",
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["deleted_audit_path"] is None
    assert any("QUADTAX_AUDIT_DIR" in w for w in r.json()["warnings"])
