"""End-to-end tests against a running server with real GitHub + Nebius APIs.

Requirements:
  - NEBIUS_API_KEY env var set (real key)
  - GITHUB_TOKEN env var set (optional, recommended)
  - Server running: uvicorn app.main:app

Run:
  pytest tests/test_e2e.py -v -s

These tests are skipped automatically if NEBIUS_API_KEY is not set or equals 'test-key'.
"""

import os
import subprocess
import pytest
from dotenv import load_dotenv

load_dotenv()  # load .env before reading any keys

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")

skip_no_key = pytest.mark.skipif(
    not NEBIUS_API_KEY or NEBIUS_API_KEY == "test-key",
    reason="NEBIUS_API_KEY not set or is test-key — skipping e2e tests",
)


def curl_post(url: str, json_body: str) -> tuple[int, str]:
    """Run curl and return (status_code, response_body)."""
    result = subprocess.run(
        [
            "curl", "-s", "-w", "\n%{http_code}",
            "-X", "POST", url,
            "-H", "Content-Type: application/json",
            "-d", json_body,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    lines = result.stdout.strip().rsplit("\n", 1)
    body = lines[0] if len(lines) > 1 else ""
    status_code = int(lines[-1])
    return status_code, body


# ---------------------------------------------------------------------------
# Happy path — real repos (curl)
# ---------------------------------------------------------------------------

@skip_no_key
class TestE2ECurl:
    """E2E tests using curl against a running server, matching the task spec."""

    def test_summarize_psf_requests(self):
        """Test with the exact repo from the task spec: psf/requests."""
        status, body = curl_post(
            f"{BASE_URL}/summarize",
            '{"github_url": "https://github.com/psf/requests"}',
        )
        assert status == 200, f"Expected 200, got {status}: {body}"

        import json
        data = json.loads(body)
        assert "summary" in data, f"Missing 'summary' field: {data}"
        assert "technologies" in data, f"Missing 'technologies' field: {data}"
        assert "structure" in data, f"Missing 'structure' field: {data}"

        assert isinstance(data["summary"], str) and len(data["summary"]) > 10
        assert isinstance(data["technologies"], list) and len(data["technologies"]) > 0
        assert isinstance(data["structure"], str) and len(data["structure"]) > 10

        # psf/requests is a Python project — "Python" should appear in technologies
        tech_lower = [t.lower() for t in data["technologies"]]
        assert "python" in tech_lower, f"Expected 'Python' in technologies: {data['technologies']}"

    def test_summarize_small_repo(self):
        """Test with a small, stable repo."""
        status, body = curl_post(
            f"{BASE_URL}/summarize",
            '{"github_url": "https://github.com/keleshev/schema"}',
        )
        assert status == 200, f"Expected 200, got {status}: {body}"

        import json
        data = json.loads(body)
        assert "summary" in data
        assert "technologies" in data
        assert "structure" in data

    def test_invalid_url_returns_error(self):
        """Non-GitHub URL returns 422 validation error."""
        status, body = curl_post(
            f"{BASE_URL}/summarize",
            '{"github_url": "not-a-url"}',
        )
        assert status == 422, f"Expected 422, got {status}: {body}"

    def test_missing_field_returns_error(self):
        """Missing github_url field returns 422."""
        status, body = curl_post(
            f"{BASE_URL}/summarize",
            '{"url": "https://github.com/psf/requests"}',
        )
        assert status == 422, f"Expected 422, got {status}: {body}"

    def test_nonexistent_repo_returns_error(self):
        """Private/nonexistent repo returns error with status and message."""
        status, body = curl_post(
            f"{BASE_URL}/summarize",
            '{"github_url": "https://github.com/nonexistent-user-abc123/nonexistent-repo-xyz789"}',
        )
        assert status in (404, 429, 502), f"Expected 404, 429 or 502, got {status}: {body}"

        import json
        data = json.loads(body)
        # Error response should have {"detail": {"status": "error", "message": "..."}}
        detail = data.get("detail", data)
        assert detail.get("status") == "error" or "message" in detail, f"Missing error format: {data}"

    def test_empty_body_returns_error(self):
        """Empty JSON body returns 422."""
        status, body = curl_post(
            f"{BASE_URL}/summarize",
            '{}',
        )
        assert status == 422, f"Expected 422, got {status}: {body}"


# ---------------------------------------------------------------------------
# Happy path — httpx (no server required, uses TestClient)
# ---------------------------------------------------------------------------

@skip_no_key
class TestE2ETestClient:
    """E2E tests using FastAPI TestClient — no separate server needed."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_summarize_fastapi_repo(self):
        """Test with fastapi/fastapi (renamed from tiangolo/fastapi)."""
        response = self.client.post(
            "/summarize",
            json={"github_url": "https://github.com/fastapi/fastapi"},
        )
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["summary"], str) and len(data["summary"]) > 10
        assert isinstance(data["technologies"], list) and len(data["technologies"]) > 0
        assert isinstance(data["structure"], str) and len(data["structure"]) > 10

        tech_lower = [t.lower() for t in data["technologies"]]
        assert "python" in tech_lower, f"Expected 'Python' in technologies: {data['technologies']}"

    def test_summarize_go_repo(self):
        """Test with a Go project to verify multi-language support."""
        response = self.client.post(
            "/summarize",
            json={"github_url": "https://github.com/junegunn/fzf"},
        )
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["summary"], str) and len(data["summary"]) > 10
        assert isinstance(data["technologies"], list) and len(data["technologies"]) > 0
        assert isinstance(data["structure"], str) and len(data["structure"]) > 10

        tech_lower = [t.lower() for t in data["technologies"]]
        assert "go" in tech_lower, f"Expected 'Go' in technologies: {data['technologies']}"

    def test_response_format_matches_spec(self):
        """Verify response exactly matches the spec: summary (str), technologies (str[]), structure (str)."""
        response = self.client.post(
            "/summarize",
            json={"github_url": "https://github.com/psf/requests"},
        )
        assert response.status_code == 200
        data = response.json()

        # Exactly these three keys (no extra top-level keys)
        assert set(data.keys()) == {"summary", "technologies", "structure"}, \
            f"Unexpected keys in response: {set(data.keys())}"

        # Type checks
        assert isinstance(data["summary"], str)
        assert isinstance(data["technologies"], list)
        assert all(isinstance(t, str) for t in data["technologies"])
        assert isinstance(data["structure"], str)

    def test_error_response_format(self):
        """Verify error response matches spec: {"status": "error", "message": "..."}."""
        response = self.client.post(
            "/summarize",
            json={"github_url": "https://github.com/nonexistent-user-abc123/nonexistent-repo-xyz789"},
        )
        assert response.status_code in (404, 429, 502)
        data = response.json()

        detail = data.get("detail", data)
        assert detail["status"] == "error"
        assert isinstance(detail["message"], str) and len(detail["message"]) > 0
