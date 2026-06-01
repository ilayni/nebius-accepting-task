# Solution Plan

## Model Choice
**Meta-Llama-3.3-70B-Instruct** — 128K context window handles large repos, strong instruction-following for structured JSON output, cost-effective on Nebius platform. (`Meta-Llama-3.1-70B-Instruct` was originally planned but is no longer available on the Nebius Token Factory API.)

## Content Extraction Strategy (The Core)

### Tier 1 — Always Include (highest signal-to-noise)
| Content | Why | Max Size |
|---------|-----|----------|
| README.md / README.rst | Best single source of project description | 3000 chars |
| Directory tree (depth 2-3) | Shows project structure at a glance | 2000 chars |
| Package manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`, `Gemfile`, `build.gradle`) | Technologies, dependencies, metadata | 2000 chars each |
| Dockerfile / docker-compose.yml | Deployment stack, services | 1500 chars |
| CI configs (`.github/workflows/*.yml`, `.gitlab-ci.yml`) | Build/test/deploy pipeline | 1500 chars |

### Tier 2 — Include If Token Budget Allows
| Content | Why | Max Size |
|---------|-----|----------|
| Entry points (`main.py`, `app.py`, `index.ts`, `cmd/main.go`, `src/lib.rs`) | Core logic, imports reveal architecture | 2000 chars |
| Config files (`.env.example`, `config/*.yaml`, `settings.py`) | Infrastructure choices | 1500 chars |
| API definitions (`openapi.yaml`, `*.proto`, `*.graphql`) | Describes service interfaces | 2000 chars |
| Key source files (largest non-test source files per directory) | Implementation patterns | 2000 chars |

### Tier 3 — Never Include (filters)
- `node_modules/`, `vendor/`, `.venv/`, `__pycache__/`, `dist/`, `build/`, `.git/`
- Binary files (images, fonts, compiled artifacts, `.woff`, `.png`, `.jpg`, `.exe`, `.so`)
- Lock files (`package-lock.json`, `poetry.lock`, `yarn.lock`, `Cargo.lock`)
- Test fixtures, snapshots, generated code
- Files > 50KB individually
- Minified files (`.min.js`, `.min.css`)

## Token Budget Management
- **Total repo content budget**: ~12,000 tokens (~48,000 chars)
- **Allocation**: Tier 1 gets priority, remaining budget goes to Tier 2
- **Truncation**: Each file is individually truncated to its max size
- **Overflow**: If Tier 1 alone exceeds budget, truncate README further and skip CI configs
- **Token estimation**: `len(text) / 4` as rough approximation

## GitHub Fetching Strategy
- **No git clone** — use GitHub REST API for speed and no disk usage
- `GET /repos/{owner}/{repo}` — repo metadata (default branch, description)
- `GET /repos/{owner}/{repo}/readme` with `Accept: application/vnd.github.raw` — README content (any variant)
- `GET /repos/{owner}/{repo}/languages` — free tech detection (learned from deer-flow)
- `GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1` — full file tree in one call
- `GET /repos/{owner}/{repo}/contents/{path}` with raw accept — individual file contents
- Optional `GITHUB_TOKEN` env var for higher rate limits (5000 vs 60 req/hr)
- Parse owner/repo from URL with regex, support various GitHub URL formats
- Fallback from `main` to `master` branch (learned from deer-flow)

## Research Sources
- **gitingest** (14K stars) — comprehensive ignore patterns (40+ dirs, 30+ extensions)
- **gitsummarize** — file size limit (100KB), `=== File: path ===` separators
- **deer-flow** (ByteDance) — dedicated readme/languages endpoints, tree capped at 100 lines

## Prompt Engineering
**System prompt**:
```
You are a code repository analyst. Analyze the provided repository content and return a JSON object with exactly these fields:
- "summary": A 2-4 sentence description of what this project does, its purpose, and key features.
- "technologies": An array of programming languages, frameworks, libraries, and tools used.
- "structure": A 2-3 sentence description of how the project is organized.
Respond ONLY with valid JSON, no markdown formatting.
```

**User prompt**:
```
Analyze this GitHub repository: {repo_url}

=== DIRECTORY STRUCTURE ===
{tree}

=== README ===
{readme_content}

=== PACKAGE MANIFEST ({manifest_name}) ===
{manifest_content}

=== CONFIGURATION FILES ===
{config_content}

=== KEY SOURCE FILES ===
{source_content}
```

## Error Handling Matrix
| Scenario | HTTP Status | Message |
|----------|-------------|---------|
| Invalid/malformed URL | 400 | "Invalid GitHub URL format" |
| Private or non-existent repo | 404 | "Repository not found or is private" |
| GitHub API rate limit | 429 | "GitHub API rate limit exceeded" |
| LLM API failure | 502 | "LLM service unavailable" |
| LLM response not valid JSON | 500 | "Failed to parse LLM response" |
| Request missing github_url | 422 | (FastAPI auto-validation) |

## Scoring Strategy Mapping
| Criterion (pts) | How we address it |
|-----------------|-------------------|
| Functionality (20) | FastAPI, Pydantic models, proper JSON responses |
| Repo processing (20) | GitHub API tree, smart file detection across 10+ ecosystems |
| Context management (20) | Tiered extraction, token budget, truncation |
| Prompt engineering (10) | Structured system prompt, clear section markers, JSON-only instruction |
| Code quality (20) | Type hints, modular design, comprehensive error handling, tests |
| Documentation (10) | README with setup, model justification, strategy explanation |
