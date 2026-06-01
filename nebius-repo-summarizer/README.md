# GitHub Repository Summarizer

A FastAPI service that accepts a GitHub repository URL and returns an LLM-generated summary describing the project's functionality, technologies, and structure.

## Setup & Run

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and set your NEBIUS_API_KEY (required)
# Optionally set GITHUB_TOKEN for higher GitHub API rate limits

# 4. Start the server
uvicorn app.main:app --reload
```

The server will be available at `http://localhost:8000`.

### Usage

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

### Run Tests

```bash
NEBIUS_API_KEY=test-key pytest tests/ -v
```

To run integration tests that make **real concurrent GitHub API calls** (LLM is still mocked):

```bash
NEBIUS_API_KEY=test-key pytest tests/test_concurrency.py -m integration -v
```

> These tests fire actual requests to the GitHub API in parallel using `asyncio.gather`. Set `GITHUB_TOKEN` to avoid hitting the unauthenticated rate limit (60 req/hr).

## Model Choice

**Meta-Llama-3.3-70B-Instruct** — chosen for its 128K context window (accommodates large repository content), strong instruction-following ability for producing structured JSON output, and favorable cost-to-quality ratio on the Nebius platform. 

## Repository Content Handling Strategy

The core challenge is selecting which repository files to send to the LLM within context window limits. The service uses a **tiered priority system with token budget management**:

### Approach: GitHub API + Tiered Extraction

Instead of cloning repositories (slow, requires disk), the service uses the GitHub REST API to fetch only what's needed:

1. **Metadata** — repo description, default branch via `GET /repos/{owner}/{repo}`
2. **README** — via dedicated `GET /repos/{owner}/{repo}/readme` endpoint (handles any README variant)
3. **Languages** — via `GET /repos/{owner}/{repo}/languages` (free technology detection)
4. **File tree** — via `GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1` (full structure in one call)
5. **Selected files** — only high-value files are fetched individually

### Three-Tier File Priority

**Tier 1 (always included):** README, directory tree (capped at 100 lines), package manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, etc.), Dockerfiles, CI configs.

**Tier 2 (included if budget allows):** Entry point files (`main.py`, `index.ts`, etc.), API definitions (`.proto`, `.graphql`, OpenAPI specs).

**Tier 3 (always excluded):** Binary files, images, lock files, `node_modules`, `vendor`, `__pycache__`, minified files, and 40+ other ignore patterns.

### Budget Management

The total content sent to the LLM is capped at ~12,000 tokens (~48,000 characters). Tier 1 content fills first, then Tier 2 uses remaining budget. Each individual file is truncated to prevent any single file from consuming the entire budget.
