"""Test baseline security headers and CORS restrictions."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_security_headers_present():
    """Every response should carry baseline hardening headers."""
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert "geolocation=()" in r.headers.get("Permissions-Policy", "")


def test_cors_restricts_methods():
    """Preflight should only advertise GET/POST, not arbitrary methods."""
    r = client.options(
        "/api/v1/submit",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    allow = r.headers.get("Access-Control-Allow-Methods", "")
    assert "DELETE" not in allow
    assert "GET" in allow
    assert "POST" in allow


def test_cors_allows_localhost_origin():
    """Localhost dev origin should be permitted."""
    r = client.get(
        "/api/v1/healthz",
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
