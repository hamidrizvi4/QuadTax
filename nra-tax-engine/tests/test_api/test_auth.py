"""Test API key authentication on protected endpoints."""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_healthz_just_works_no_key():
    """Known public endpoint remains open."""
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200


def test_auth_fails_closed_if_key_unset():
    """Server fails closed (503) if QUADTAX_API_KEY is not configured."""
    with patch.dict(os.environ, {"QUADTAX_API_KEY": ""}):
        r = client.post(
            "/api/v1/submit",
            json={"intake": {"identity": {"filing_status": "single"}}},
        )
        assert r.status_code == 503
        assert "authentication not configured" in r.json()["detail"]


def test_auth_401_if_header_missing():
    """Missing Authorization header → 401."""
    with patch.dict(os.environ, {"QUADTAX_API_KEY": "secret123"}):
        r = client.post(
            "/api/v1/submit",
            json={"intake": {"identity": {"filing_status": "single"}}},
        )
        assert r.status_code == 401
        assert "Missing API key" in r.json()["detail"]


def test_auth_401_if_invalid():
    """Invalid token → 401."""
    with patch.dict(os.environ, {"QUADTAX_API_KEY": "secret123"}):
        r = client.post(
            "/api/v1/submit",
            json={"intake": {"identity": {"filing_status": "single"}}},
            headers={"Authorization": "Bearer wrong"},
        )
        assert r.status_code == 401
        assert "Invalid API key" in r.json()["detail"]


def test_auth_passes_with_valid_key():
    """Valid token must not get 401 (body validation is irrelevant here)."""
    with patch.dict(os.environ, {"QUADTAX_API_KEY": "secret123"}):
        r = client.post(
            "/api/v1/submit",
            json={"intake": {}},  # missing required sub-fields → 422, but auth passes
            headers={"Authorization": "Bearer secret123"},
        )
        assert r.status_code != 401  # auth passed


def test_auth_on_ocr():
    """OCR endpoint protected too — valid key must not get 401."""
    with patch.dict(os.environ, {"QUADTAX_API_KEY": "secret123"}):
        with patch("src.api.ocr_endpoint.DocumentExtractor") as mock_ext:
            mock_ext.return_value.extract_all.return_value = {
                "i94": None,
                "w2s": [],
                "form_1042s": [],
                "form_1099s": [],
            }
            r = client.post(
                "/api/v1/ocr",
                data={"tax_year": "2025"},
                headers={"Authorization": "Bearer secret123"},
            )
            assert r.status_code != 401  # auth passed


def test_auth_on_packet():
    """Packet endpoint protected too — valid key must not get 401."""
    with patch.dict(os.environ, {"QUADTAX_API_KEY": "secret123"}):
        r = client.get(
            "/api/v1/packet",
            params={"path": "outputs/x.pdf"},
            headers={"Authorization": "Bearer secret123"},
        )
        assert r.status_code != 401  # auth passed
