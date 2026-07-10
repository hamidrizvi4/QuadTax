"""Test for path traversal vulnerability in /api/v1/packet endpoint."""

import os

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_path_traversal_blocks_relative():
    """Attempt to traverse from outputs/ to parent directory."""
    # This should be blocked: ../../etc/passwd
    response = client.get(
        "/api/v1/packet?path=../../../etc/passwd",
        headers={"Authorization": "Bearer test-key-not-a-secret"},
    )
    assert response.status_code == 403


def test_path_traversal_blocks_external_prefix():
    """Block paths like 'outputs_evil/file.pdf' that start with 'outputs/'."""
    # This path starts with 'outputs' but is not under outputs/ directory.
    response = client.get(
        "/api/v1/packet?path=outputs_evil/file.pdf",
        headers={"Authorization": "Bearer test-key-not-a-secret"},
    )
    assert response.status_code == 403


def test_path_traversal_allows_valid():
    """Allow paths under outputs/ directory."""
    # Create a real file under outputs/ so FileResponse's existence check passes.
    os.makedirs("outputs", exist_ok=True)
    real_file = os.path.join("outputs", "user_1040-NR.pdf")
    with open(real_file, "w") as f:
        f.write("%PDF-1.4 test")
    try:
        response = client.get(
            "/api/v1/packet?path=" + real_file,
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert response.status_code == 200
    finally:
        if os.path.exists(real_file):
            os.remove(real_file)