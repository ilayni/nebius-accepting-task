# Implementation Tasks

## Setup
- [x] Initialize project structure (`app/` package with modules)
- [x] Create `requirements.txt` (fastapi, uvicorn, openai, httpx, python-dotenv, pytest, pytest-asyncio)
- [x] Create `.env.example` and `.gitignore`
- [x] Set up `app/config.py` with env var loading

## Core Logic
- [x] `app/models.py` — Pydantic request/response schemas
- [x] `app/github_client.py` — URL parsing, repo metadata, readme, languages, tree fetching, file content
- [x] `app/content_extractor.py` — Tier 1/2/3 classification, ignore patterns, file selection, budget management
- [x] `app/llm_client.py` — Nebius API via OpenAI SDK, prompt building, JSON response parsing
- [x] `app/main.py` — FastAPI app, `/summarize` endpoint, error handling

## Testing
- [x] `tests/test_github_client.py` — URL parsing (10 test cases)
- [x] `tests/test_content_extractor.py` — ignore, classify, tree, select, budget (28 test cases)
- [x] `tests/test_llm_client.py` — response parsing (7 test cases)
- [x] `tests/test_api.py` — endpoint integration with mocks (5 test cases)
- [x] All 56 tests passing

## Documentation
- [x] `README.md` — setup instructions, model justification, strategy description
- [x] `arch.md` — architecture diagram and component descriptions (updated with research)

## Final
- [x] End-to-end test with real GitHub repos (requires NEBIUS_API_KEY)
- [ ] Review error responses match spec format
- [ ] Package as zip for submission
