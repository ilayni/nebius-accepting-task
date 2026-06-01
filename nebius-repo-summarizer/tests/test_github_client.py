"""Tests for GitHub API client."""

import pytest

from app.github_client import parse_github_url


class TestParseGitHubUrl:
    def test_basic_url(self):
        assert parse_github_url("https://github.com/psf/requests") == ("psf", "requests")

    def test_url_with_trailing_slash(self):
        assert parse_github_url("https://github.com/psf/requests/") == ("psf", "requests")

    def test_url_with_git_suffix(self):
        assert parse_github_url("https://github.com/psf/requests.git") == ("psf", "requests")

    def test_url_with_tree_path(self):
        assert parse_github_url("https://github.com/psf/requests/tree/main/src") == ("psf", "requests")

    def test_http_url(self):
        assert parse_github_url("http://github.com/psf/requests") == ("psf", "requests")

    def test_owner_with_dots(self):
        assert parse_github_url("https://github.com/some.org/my-repo") == ("some.org", "my-repo")

    def test_owner_with_hyphens(self):
        assert parse_github_url("https://github.com/my-org/my-repo") == ("my-org", "my-repo")

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_github_url("https://gitlab.com/owner/repo")

    def test_empty_url_raises(self):
        with pytest.raises(ValueError):
            parse_github_url("")

    def test_no_repo_raises(self):
        with pytest.raises(ValueError):
            parse_github_url("https://github.com/owner")
