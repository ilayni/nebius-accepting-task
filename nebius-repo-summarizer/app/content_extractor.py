"""Smart content extraction with tiered priority and token budget management."""

import fnmatch
import logging
from dataclasses import dataclass, field

from app.config import MAX_CONTENT_CHARS, MAX_FILE_SIZE, MAX_TREE_LINES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ignore patterns (adopted from gitingest's comprehensive set)
# ---------------------------------------------------------------------------
IGNORE_DIRS: set[str] = {
    "node_modules", "__pycache__", ".git", ".svn", ".hg",
    "venv", ".venv", "env", "virtualenv", "site-packages",
    "dist", "build", "target", "out", ".next", ".nuxt", ".docusaurus",
    "vendor", ".bundle", ".build",
    ".idea", ".vscode", ".vs", ".settings",
    ".cache", ".sass-cache", ".eslintcache",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox",
    ".gradle", ".npm", ".yarn", ".pnpm-store",
    "obj", "bin", "pkg",
    "xcuserdata", ".swiftpm",
    "coverage", ".nyc_output",
}

IGNORE_EXTENSIONS: set[str] = {
    # Compiled / binary
    ".pyc", ".pyo", ".pyd", ".class", ".jar", ".war", ".ear",
    ".o", ".obj", ".dll", ".dylib", ".exe", ".lib", ".so", ".a",
    ".bin", ".pdb", ".whl", ".egg",
    # Media
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".bmp", ".webp",
    ".pdf", ".mov", ".mp4", ".mp3", ".wav", ".avi", ".flv",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Minified / maps
    ".min.js", ".min.css", ".map",
    # Database
    ".db", ".sqlite", ".sqlite3",
    # Temp
    ".log", ".bak", ".swp", ".tmp", ".temp",
    # OS
    ".DS_Store",
}

IGNORE_FILES: set[str] = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "Cargo.lock",
    "Gemfile.lock", "composer.lock",
    "bun.lock", "bun.lockb",
    "go.sum",
    ".gitignore", ".gitattributes", ".gitmodules",
    "Thumbs.db", "desktop.ini",
}

# ---------------------------------------------------------------------------
# Tier 1: Always fetch these (highest signal-to-noise)
# ---------------------------------------------------------------------------
TIER1_MANIFESTS: set[str] = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "Gemfile", "composer.json", "mix.exs", "pubspec.yaml",
    "Makefile", "CMakeLists.txt",
    "requirements.txt",
}

TIER1_INFRA: set[str] = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
}

TIER1_CI_PATTERNS: list[str] = [
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".gitlab-ci.yml",
    ".travis.yml",
    ".circleci/config.yml",
    "Jenkinsfile",
]

# ---------------------------------------------------------------------------
# Tier 2: Include if token budget allows
# ---------------------------------------------------------------------------
TIER2_ENTRY_POINTS: set[str] = {
    "main.py", "app.py", "index.ts", "index.js", "index.tsx",
    "main.go", "main.rs", "lib.rs", "Main.java", "Program.cs",
    "manage.py", "wsgi.py", "asgi.py",
}

TIER2_API_DEFS: set[str] = {
    "openapi.yaml", "openapi.yml", "openapi.json",
    "swagger.yaml", "swagger.yml", "swagger.json",
}

TIER2_API_EXTENSIONS: set[str] = {".proto", ".graphql", ".gql"}


@dataclass
class ExtractedContent:
    """Container for all extracted repo content."""
    readme: str = ""
    tree_text: str = ""
    languages: dict[str, int] = field(default_factory=dict)
    tier1_files: dict[str, str] = field(default_factory=dict)  # path -> content
    tier2_files: dict[str, str] = field(default_factory=dict)


def should_ignore(path: str) -> bool:
    """Check if a file path should be excluded."""
    parts = path.split("/")

    # Check all path components against ignored directories
    for part in parts:
        if part in IGNORE_DIRS:
            return True

    filename = parts[-1]

    # Check exact filename matches
    if filename in IGNORE_FILES:
        return True

    # Check extension patterns
    for ext in IGNORE_EXTENSIONS:
        if filename.endswith(ext):
            return True

    return False


def classify_file(path: str) -> int:
    """Classify a file into tier 1, 2, or 0 (not prioritized).

    Returns:
        1 for tier 1, 2 for tier 2, 0 for regular files
    """
    filename = path.split("/")[-1]

    # Tier 1: manifests and infra
    if filename in TIER1_MANIFESTS or filename in TIER1_INFRA:
        return 1

    # Tier 1: CI configs
    for pattern in TIER1_CI_PATTERNS:
        if fnmatch.fnmatch(path, pattern):
            return 1

    # Tier 2: entry points (only at root or src/ or cmd/ depth)
    depth = path.count("/")
    if filename in TIER2_ENTRY_POINTS and depth <= 2:
        return 2

    # Tier 2: API definitions
    if filename in TIER2_API_DEFS:
        return 2
    for ext in TIER2_API_EXTENSIONS:
        if filename.endswith(ext):
            return 2

    return 0


def build_tree_text(tree: list[dict], max_lines: int = MAX_TREE_LINES) -> str:
    """Build a directory tree string from GitHub API tree data.

    Filters out ignored paths and caps output at max_lines.
    """
    lines: list[str] = []
    for item in tree:
        if should_ignore(item["path"]):
            continue

        depth = item["path"].count("/")
        if depth > 3:
            continue

        indent = "  " * depth
        name = item["path"].split("/")[-1]
        suffix = "/" if item["type"] == "tree" else ""
        lines.append(f"{indent}{name}{suffix}")

        if len(lines) >= max_lines:
            lines.append("  ... (truncated)")
            break

    return "\n".join(lines)


def select_files(tree: list[dict]) -> tuple[list[str], list[str]]:
    """Select tier 1 and tier 2 file paths from the tree.

    Returns:
        (tier1_paths, tier2_paths)
    """
    tier1: list[str] = []
    tier2: list[str] = []

    for item in tree:
        if item["type"] != "blob":
            continue
        if should_ignore(item["path"]):
            continue
        size = item.get("size", 0)
        if size > MAX_FILE_SIZE:
            continue

        tier = classify_file(item["path"])
        if tier == 1:
            tier1.append(item["path"])
        elif tier == 2:
            tier2.append(item["path"])

    return tier1, tier2


def truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, adding a marker if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


def build_prompt_content(content: ExtractedContent) -> str:
    """Assemble all extracted content into a structured prompt string.

    Respects the overall token budget by filling tier 1 first, then tier 2.
    """
    parts: list[str] = []
    budget = MAX_CONTENT_CHARS

    # Languages (always cheap, ~100 chars)
    if content.languages:
        lang_str = ", ".join(
            f"{lang} ({bytes_:,} bytes)" for lang, bytes_ in
            sorted(content.languages.items(), key=lambda x: -x[1])[:10]
        )
        section = f"=== LANGUAGES ===\n{lang_str}"
        parts.append(section)
        budget -= len(section)

    # Directory tree
    if content.tree_text:
        tree_section = f"=== DIRECTORY STRUCTURE ===\n{truncate(content.tree_text, min(3000, budget))}"
        parts.append(tree_section)
        budget -= len(tree_section)

    # README
    if content.readme:
        readme_section = f"=== README ===\n{truncate(content.readme, min(4000, budget))}"
        parts.append(readme_section)
        budget -= len(readme_section)

    # Tier 1 files
    for path, file_content in content.tier1_files.items():
        if budget <= 0:
            break
        section = f"=== {path} ===\n{truncate(file_content, min(2000, budget))}"
        parts.append(section)
        budget -= len(section)

    # Tier 2 files (only if budget remains)
    for path, file_content in content.tier2_files.items():
        if budget <= 500:  # keep some buffer
            break
        section = f"=== {path} ===\n{truncate(file_content, min(2000, budget))}"
        parts.append(section)
        budget -= len(section)

    return "\n\n".join(parts)
