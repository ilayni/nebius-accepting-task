# Nebius AI Performance Engineering — Extended Project Context

## Task Source
https://taskchecker.academy.nebius.com/tasks/ai-performance-engineering-2026

## What We're Building
A Python FastAPI service with a single `POST /summarize` endpoint that:
1. Accepts `{ "github_url": "https://github.com/owner/repo" }`
2. Fetches repo content via GitHub API (no cloning)
3. Intelligently selects the most informative files (tiered priority)
4. Sends extracted content to Nebius LLM for analysis
5. Returns `{ "summary": "...", "technologies": [...], "structure": "..." }`

## Nebius Token Factory API
- **Base URL**: `https://api.tokenfactory.nebius.com/v1/`
- **Auth**: `Authorization: Bearer <NEBIUS_API_KEY>`
- **Compatibility**: OpenAI-compatible (use `openai` Python SDK with custom `base_url`)
- **Model**: `meta-llama/Llama-3.3-70B-Instruct` (updated from `Meta-Llama-3.1-70B-Instruct`, which is no longer available)
  - 128K context window
- **Endpoint**: `POST /chat/completions`

## Evaluation Criteria (100 points)
| Criterion | Points | Our Strategy |
|-----------|--------|-------------|
| Functionality | 20 | FastAPI + proper request/response models |
| Repository processing | 20 | GitHub API tree endpoint, smart file filtering |
| Context management | 20 | Tiered extraction with token budget tracking |
| Prompt engineering | 10 | Structured system prompt, JSON output instructions |
| Code quality & error handling | 20 | Type hints, Pydantic, proper HTTP status codes |
| Documentation | 10 | README with setup, model justification, strategy |

**Blocking requirements** (must pass or score = 0):
- Server starts per README instructions
- `/summarize` endpoint exists and accepts POST
- Returns valid JSON responses
- Uses Nebius API (not local models)

## Content Extraction Strategy
See `plan.md` for the full tiered approach (Tier 1: always include, Tier 2: budget permitting, Tier 3: never include).

## Folder Layout
```
nebius/
├── CLAUDE.md                          # auto-loaded, concise
├── cld_mgmt/                          # internal planning (not submitted)
│   ├── CLAUDE.md                      # this file
│   ├── plan.md                        # solution strategy
│   └── tasks.md                       # implementation checklist
└── nebius-repo-summarizer/            # submission folder
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                    # FastAPI app + endpoint
    │   ├── github_client.py           # GitHub API fetching
    │   ├── content_extractor.py       # Smart file selection
    │   ├── llm_client.py             # Nebius API integration
    │   └── models.py                  # Pydantic schemas
    ├── tests/
    │   ├── __init__.py
    │   ├── test_api.py
    │   ├── test_github_client.py
    │   ├── test_content_extractor.py
    │   └── test_llm_client.py
    ├── .env.example
    ├── .gitignore
    ├── arch.md
    ├── requirements.txt
    └── README.md
```

## Key Commands
```bash
cd nebius-repo-summarizer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in API keys
uvicorn app.main:app --reload
pytest tests/ -v
```
