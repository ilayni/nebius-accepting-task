"""Integration tests for the /summarize endpoint."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


# Patch config before importing app to avoid requiring NEBIUS_API_KEY in tests
with patch.dict("os.environ", {"NEBIUS_API_KEY": "test-key"}):
    from app.main import app

client = TestClient(app)


class TestSummarizeEndpoint:
    def test_invalid_url_returns_422(self):
        """Missing github_url or malformed URL returns validation error."""
        response = client.post("/summarize", json={"github_url": "not-a-url"})
        assert response.status_code == 422

    def test_missing_body_returns_422(self):
        response = client.post("/summarize", json={})
        assert response.status_code == 422

    def test_missing_field_returns_422(self):
        response = client.post("/summarize", json={"url": "https://github.com/psf/requests"})
        assert response.status_code == 422

    @patch("app.main.GitHubClient")
    @patch("app.main.LLMClient")
    def test_happy_path(self, MockLLM, MockGH):
        """Valid URL with mocked GitHub and LLM returns correct response."""
        # Mock GitHub client
        gh_instance = MockGH.return_value
        gh_instance.get_repo_info = AsyncMock(return_value={"default_branch": "main"})
        gh_instance.get_readme = AsyncMock(return_value="# Requests\nHTTP library.")
        gh_instance.get_languages = AsyncMock(return_value={"Python": 50000})
        gh_instance.get_tree = AsyncMock(return_value=[
            {"path": "src", "type": "tree"},
            {"path": "src/main.py", "type": "blob", "size": 1000},
            {"path": "requirements.txt", "type": "blob", "size": 200},
        ])
        gh_instance.get_file_content = AsyncMock(return_value="flask==3.0")
        gh_instance.close = AsyncMock()

        # Mock LLM client
        llm_instance = MockLLM.return_value
        llm_instance.summarize = AsyncMock(return_value={
            "summary": "A Python HTTP library.",
            "technologies": ["Python", "urllib3"],
            "structure": "Standard Python package layout.",
        })

        response = client.post("/summarize", json={"github_url": "https://github.com/psf/requests"})
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "technologies" in data
        assert "structure" in data
        assert isinstance(data["technologies"], list)

    @patch("app.main.GitHubClient")
    def test_github_404_returns_error(self, MockGH):
        """Non-existent repo returns proper error response."""
        from app.github_client import GitHubClientError

        gh_instance = MockGH.return_value
        gh_instance.get_repo_info = AsyncMock(side_effect=GitHubClientError("Repository not found or is private", 404))
        gh_instance.close = AsyncMock()

        response = client.post("/summarize", json={"github_url": "https://github.com/nonexistent/repo"})
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["status"] == "error"
