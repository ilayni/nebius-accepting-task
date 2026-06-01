"""Concurrency tests for the POST /summarize endpoint.

Part 1 (mocked): Verifies the FastAPI app handles simultaneous in-flight requests
correctly — no shared-state corruption, no deadlocks. Runs by default.

Part 2 (integration): Fires real GitHub API calls with mocked LLM.
Excluded from the default run. Enable with: pytest -m integration
"""

import asyncio
import os

import pytest
import pytest_asyncio  # noqa: F401 — ensures asyncio mode is available
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

with patch.dict("os.environ", {"NEBIUS_API_KEY": os.getenv("NEBIUS_API_KEY", "test-key")}):
    from app.main import app
from app.github_client import GitHubClientError

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

VALID_URL = "https://github.com/a/b"

_GH_TREE = [
    {"path": "src", "type": "tree"},
    {"path": "src/main.py", "type": "blob", "size": 500},
    {"path": "requirements.txt", "type": "blob", "size": 100},
]

_LLM_RESULT = {
    "summary": "A test repository.",
    "technologies": ["Python"],
    "structure": "Standard layout.",
}


def make_gh_mock() -> AsyncMock:
    """Return a configured AsyncMock mimicking GitHubClient."""
    m = AsyncMock()
    m.get_repo_info = AsyncMock(return_value={"default_branch": "main"})
    m.get_readme = AsyncMock(return_value="# Test Repo")
    m.get_languages = AsyncMock(return_value={"Python": 10000})
    m.get_tree = AsyncMock(return_value=_GH_TREE)
    m.get_file_content = AsyncMock(return_value="content")
    m.close = AsyncMock()
    return m


def make_llm_mock() -> AsyncMock:
    """Return a configured AsyncMock mimicking LLMClient."""
    m = AsyncMock()
    m.summarize = AsyncMock(return_value=_LLM_RESULT)
    return m


# ---------------------------------------------------------------------------
# Part 1 — Mocked concurrency tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_happy_path():
    """20 concurrent valid requests all return 200 with correct schema."""
    N = 20
    with patch("app.main.GitHubClient", return_value=make_gh_mock()), \
         patch("app.main.LLMClient", return_value=make_llm_mock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tasks = [client.post("/summarize", json={"github_url": VALID_URL}) for _ in range(N)]
            responses = await asyncio.gather(*tasks)

    assert len(responses) == N
    for resp in responses:
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "technologies" in data
        assert isinstance(data["technologies"], list)
        assert "structure" in data


@pytest.mark.asyncio
async def test_concurrent_invalid_urls():
    """20 concurrent requests with invalid URLs all return 422 (Pydantic rejects them)."""
    N = 20
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tasks = [client.post("/summarize", json={"github_url": "not-a-url"}) for _ in range(N)]
        responses = await asyncio.gather(*tasks)

    assert len(responses) == N
    for resp in responses:
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_mixed_requests():
    """10 valid + 10 invalid concurrent requests: valid→200, invalid→422, no bleed."""
    N_VALID = 10
    N_INVALID = 10

    with patch("app.main.GitHubClient", return_value=make_gh_mock()), \
         patch("app.main.LLMClient", return_value=make_llm_mock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            valid_tasks = [
                client.post("/summarize", json={"github_url": VALID_URL})
                for _ in range(N_VALID)
            ]
            invalid_tasks = [
                client.post("/summarize", json={"github_url": "not-a-url"})
                for _ in range(N_INVALID)
            ]
            all_tasks = valid_tasks + invalid_tasks
            responses = await asyncio.gather(*all_tasks)

    valid_responses = responses[:N_VALID]
    invalid_responses = responses[N_VALID:]

    for resp in valid_responses:
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "technologies" in data
        assert "structure" in data

    for resp in invalid_responses:
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_github_errors():
    """20 concurrent requests where GitHub raises 404 — all return 404 with correct error shape."""
    N = 20
    gh_mock = make_gh_mock()
    gh_mock.get_repo_info = AsyncMock(
        side_effect=GitHubClientError("Repository not found or is private", 404)
    )

    with patch("app.main.GitHubClient", return_value=gh_mock), \
         patch("app.main.LLMClient", return_value=make_llm_mock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tasks = [client.post("/summarize", json={"github_url": VALID_URL}) for _ in range(N)]
            responses = await asyncio.gather(*tasks)

    assert len(responses) == N
    for resp in responses:
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["status"] == "error"
        assert "message" in detail


@pytest.mark.asyncio
async def test_concurrent_slow_responses_no_deadlock():
    """10 concurrent requests with a slow GitHub mock all complete without deadlock."""
    N = 10

    async def slow_get_repo_info(owner, repo):
        await asyncio.sleep(0.01)
        return {"default_branch": "main"}

    gh_mock = make_gh_mock()
    gh_mock.get_repo_info = slow_get_repo_info

    with patch("app.main.GitHubClient", return_value=gh_mock), \
         patch("app.main.LLMClient", return_value=make_llm_mock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tasks = [client.post("/summarize", json={"github_url": VALID_URL}) for _ in range(N)]
            responses = await asyncio.gather(*tasks)

    assert len(responses) == N
    for resp in responses:
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Part 2 — Real GitHub integration test (excluded by default)
# ---------------------------------------------------------------------------

INTEGRATION_REPO = "https://github.com/encode/httpx"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_github_concurrent():
    """
    Fires 3 real concurrent GitHub API calls. Requires network access.
    Run with: pytest -m integration
    LLM is mocked; only GitHub calls are real.
    Rate limit note: uses ~15 GitHub API calls (~3 req × 5 calls each).
    Safe for unauthenticated use (60 req/hr limit). Set GITHUB_TOKEN for more headroom.
    """
    N = 3

    with patch("app.main.LLMClient", return_value=make_llm_mock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tasks = [
                client.post("/summarize", json={"github_url": INTEGRATION_REPO})
                for _ in range(N)
            ]
            responses = await asyncio.gather(*tasks)

    assert len(responses) == N
    for resp in responses:
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert isinstance(data["technologies"], list)
        assert "structure" in data
