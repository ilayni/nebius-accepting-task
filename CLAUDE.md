# Nebius AI Performance Engineering — Admission Task

## Project
Build a FastAPI service (`POST /summarize`) that accepts a GitHub repo URL and returns an LLM-generated summary with technologies and structure.

## Layout
- `nebius-repo-summarizer/` — submission code (Python 3.10+, FastAPI)
- `cld_mgmt/` — internal planning & tracking (not submitted)

## Key Commands
```bash
cd nebius-repo-summarizer
pip install -r requirements.txt
uvicorn app.main:app --reload          # run server
pytest tests/                           # run tests
```

## Environment
- `NEBIUS_API_KEY` — required, from https://studio.nebius.com
- `GITHUB_TOKEN` — optional, increases GitHub API rate limit

## API
- Nebius base URL: `https://api.tokenfactory.nebius.com/v1/`
- OpenAI-compatible (use `openai` Python SDK)
- Model: `meta-llama/Llama-3.3-70B-Instruct` (128K context)

## Conventions
- Python 3.10+, type hints, Pydantic models
- Tests with pytest + FastAPI TestClient
- Config via environment variables (python-dotenv)
