# Architecture

## Overview
The service is a single-endpoint FastAPI application that summarizes GitHub repositories using an LLM. 
It avoids cloning repos entirely, instead using the GitHub REST API to fetch repository metadata, directory trees, and selected file contents. 
A tiered content extraction system prioritizes the most informative files while respecting LLM context window limits. The extracted content is sent to the Nebius Token Factory API (OpenAI-compatible) for analysis.

## Block Diagram

```
                          POST /summarize
                          { github_url }
                               │
                               ▼
                    ┌─────────────────────┐
                    │   URL Validation    │
                    │   Parse owner/repo  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   GitHub REST API   │
                    │                     │
                    │  1. GET /repos/     │──── repo metadata
                    │     {owner}/{repo}  │     (default branch,
                    │                     │      description)
                    │  2. GET /git/trees/ │──── full file tree
                    │     {branch}?       │     (recursive)
                    │     recursive=1     │
                    │                     │
                    │  3. GET /readme     │──── README content
                    │     (raw accept)    │     (any variant)
                    │                     │
                    │  4. GET /languages  │──── tech detection
                    │                     │     (free endpoint)
                    │                     │
                    │  5. GET /contents/  │──── selected file
                    │     {path}          │     contents (raw)
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Content Extractor  │
                    │                     │
                    │  Tier 1 (always):   │
                    │  - README           │
                    │  - Directory tree   │
                    │  - Package manifest │
                    │  - Dockerfile       │
                    │  - CI config        │
                    │                     │
                    │  Tier 2 (if budget):│
                    │  - Entry points     │
                    │  - API definitions  │
                    │  - Key source files │
                    │                     │
                    │  Tier 3 (exclude):  │
                    │  - node_modules     │
                    │  - binaries/locks   │
                    │  - generated code   │
                    │                     │
                    │  Token budget:      │
                    │  ~12,000 tokens     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Prompt Builder    │
                    │                     │
                    │  System: "You are   │
                    │  a repo analyst..." │
                    │                     │
                    │  User: Structured   │
                    │  sections with      │
                    │  === markers ===    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Nebius LLM API    │
                    │                     │
                    │  POST /v1/chat/     │
                    │    completions      │
                    │                     │
                    │  Model: Llama-3.3-  │
                    │    70B-Instruct     │
                    │                     │
                    │  OpenAI SDK with    │
                    │  custom base_url    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Response Parser    │
                    │                     │
                    │  Parse JSON from    │
                    │  LLM output         │
                    │  Validate fields    │
                    └──────────┬──────────┘
                               │
                               ▼
                    { summary, technologies, structure }
```

## Components

### `main.py` — FastAPI Application
The entry point. Defines the `POST /summarize` endpoint, wires together all components, and handles HTTP error responses. Uses Pydantic models for request/response validation.

### `github_client.py` — GitHub API Client
Handles all interaction with GitHub's REST API. Parses various GitHub URL formats into owner/repo. Fetches repo metadata (to get the default branch), the recursive file tree (single API call), and individual file contents. Supports optional authentication via `GITHUB_TOKEN` for higher rate limits. The HTTP client follows redirects automatically (`follow_redirects=True`) to handle renamed or transferred repositories that return 301 responses.

### `content_extractor.py` — Smart Content Selection
The core differentiator. Classifies files into tiers based on filename patterns and paths. Manages a token budget (~12,000 tokens) and fills it with Tier 1 content first, then Tier 2. Truncates individual files to prevent any single file from consuming the entire budget. Filters out binary files, lock files, vendored dependencies, and build artifacts.

### `llm_client.py` — Nebius LLM Integration
Builds structured prompts from extracted content and sends them to the Nebius Token Factory API using the OpenAI Python SDK (compatible endpoint). Parses the JSON response and validates it contains the required fields.

### `models.py` — Data Models
Pydantic schemas for the API request (`SummarizeRequest`), success response (`SummarizeResponse`), and error response (`ErrorResponse`).

## Key Design Decisions

1. **GitHub API over git clone** — Faster (no disk I/O), works without git installed, avoids downloading entire repo history. The tree endpoint returns the full structure in a single API call.

2. **Tiered content extraction** — Not all files are equal. README and manifests carry more information-per-token than arbitrary source files. The tiered system ensures the LLM always sees the highest-value content.

3. **Token budget management** — Rather than sending everything and hoping it fits, we allocate a fixed budget and fill it greedily by priority. This produces consistent results regardless of repo size.

4. **OpenAI SDK for Nebius** — Since the Nebius API is OpenAI-compatible, we use the official `openai` Python package with a custom `base_url`. This gives us a well-tested client with retry logic, streaming support, and type safety for free.

5. **Dedicated GitHub endpoints** — Uses `/repos/{owner}/{repo}/readme` (handles any README variant automatically) and `/repos/{owner}/{repo}/languages` (free technology detection without parsing manifests). Inspired by ByteDance's deer-flow project.

6. **Comprehensive ignore patterns** — Adopted from gitingest (14K stars): 40+ directory patterns, 30+ file extension patterns, and specific lock file exclusions covering Python, Node, Go, Rust, Java, Ruby, Swift, .NET, and more.
