# Nebius Course — Tooling & Utilities

Supporting tools developed during the Nebius ML course.

## Contents

### `nebius-repo-summarizer/`
A FastAPI service that summarizes GitHub repositories using the Nebius LLM API. Given a repo URL, it extracts key files and generates a structured summary.

- `app/` — FastAPI application (main, models, config, clients)
- `tests/` — unit and integration tests
- `requirements.txt` — dependencies
- `.env.example` — required environment variables template

### `cld_mgmt/`
Cloud management task instructions and planning docs.

### Utility scripts
- `create_submission_zip.sh` — packages a project for submission
- `test_submission.sh` — validates a submission package
