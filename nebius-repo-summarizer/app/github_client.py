"""GitHub REST API client for fetching repository content."""

import re
import logging

import httpx

from app.config import GITHUB_TOKEN

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "repo-summarizer/1.0"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL.

    Handles formats:
      https://github.com/owner/repo
      https://github.com/owner/repo.git
      https://github.com/owner/repo/tree/main/some/path
    """
    url = url.rstrip("/")
    match = re.match(r"https?://github\.com/([\w.\-]+)/([\w.\-]+)", url)
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    owner = match.group(1)
    repo = match.group(2).removesuffix(".git")
    return owner, repo


class GitHubClientError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class GitHubClient:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(headers=_headers(), timeout=30.0, follow_redirects=True)

    async def close(self) -> None:
        await self.client.aclose()

    async def _get(self, url: str, accept: str | None = None) -> httpx.Response:
        headers = {"Accept": accept} if accept else {}
        resp = await self.client.get(url, headers=headers)
        if resp.status_code == 404:
            raise GitHubClientError("Repository not found or is private", 404)
        if resp.status_code in (403, 429):
            raise GitHubClientError("GitHub API rate limit exceeded. Set GITHUB_TOKEN for higher limits.", 429)
        if resp.status_code != 200:
            raise GitHubClientError(f"GitHub API error: {resp.status_code}", 502)
        return resp

    async def get_repo_info(self, owner: str, repo: str) -> dict:
        """Fetch repository metadata (description, default branch, etc.)."""
        resp = await self._get(f"{GITHUB_API}/repos/{owner}/{repo}")
        return resp.json()

    async def get_readme(self, owner: str, repo: str) -> str:
        """Fetch README content as raw text (handles README.md, readme.rst, etc.)."""
        try:
            resp = await self._get(
                f"{GITHUB_API}/repos/{owner}/{repo}/readme",
                accept="application/vnd.github.raw",
            )
            return resp.text
        except GitHubClientError:
            return ""

    async def get_languages(self, owner: str, repo: str) -> dict[str, int]:
        """Fetch language breakdown (language -> bytes)."""
        try:
            resp = await self._get(f"{GITHUB_API}/repos/{owner}/{repo}/languages")
            return resp.json()
        except GitHubClientError:
            return {}

    async def get_tree(self, owner: str, repo: str, branch: str) -> list[dict]:
        """Fetch the full recursive file tree. Falls back from main to master."""
        try:
            resp = await self._get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            )
            return resp.json().get("tree", [])
        except GitHubClientError:
            if branch == "main":
                return await self.get_tree(owner, repo, "master")
            raise

    async def get_file_content(self, owner: str, repo: str, path: str) -> str:
        """Fetch raw content of a single file."""
        resp = await self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            accept="application/vnd.github.raw",
        )
        return resp.text
