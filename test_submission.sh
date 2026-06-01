#!/usr/bin/env bash
# =============================================================================
# test_submission.sh — Validate nebius-repo-summarizer zip submission
#
# Tests compliance with task_instrunctions.md:
#   - "What to Submit" (required files, README content)
#   - "How Your Code Should Run" (install, start, curl, env var)
#   - "Blocking Criteria" (server starts, endpoint exists, returns response)
#   - Response/error format validation
#
# Usage:
#   ./test_submission.sh <path-to-zip> [NEBIUS_API_KEY] [GITHUB_TOKEN]
#
# If API keys are not passed as arguments, the script reads them from
#   ../nebius-repo-summarizer/.env  (relative to the script location)
#
# Requirements: python3, curl, jq, unzip
# =============================================================================

set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass()  { echo -e "  ${GREEN}PASS${NC}  $1"; PASSES=$((PASSES+1)); }
fail()  { echo -e "  ${RED}FAIL${NC}  $1"; FAILURES=$((FAILURES+1)); }
warn()  { echo -e "  ${YELLOW}WARN${NC}  $1"; }
info()  { echo -e "  ···   $1"; }

PASSES=0; FAILURES=0

# ── args & env ───────────────────────────────────────────────────────────────
ZIP_PATH="${1:-}"
if [[ -z "$ZIP_PATH" || ! -f "$ZIP_PATH" ]]; then
  echo "Usage: $0 <path-to-zip> [NEBIUS_API_KEY] [GITHUB_TOKEN]"
  exit 1
fi
ZIP_PATH="$(cd "$(dirname "$ZIP_PATH")" && pwd)/$(basename "$ZIP_PATH")"

NEBIUS_API_KEY="${2:-}"
GITHUB_TOKEN="${3:-}"

# Try loading from .env if not provided
if [[ -z "$NEBIUS_API_KEY" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  ENV_FILE="$SCRIPT_DIR/nebius-repo-summarizer/.env"
  if [[ -f "$ENV_FILE" ]]; then
    info "Loading API keys from $ENV_FILE"
    set -a; source "$ENV_FILE"; set +a
  fi
fi

if [[ -z "${NEBIUS_API_KEY:-}" ]]; then
  echo "ERROR: NEBIUS_API_KEY is required. Pass as arg or set in .env"
  exit 1
fi

export NEBIUS_API_KEY
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# ── temp workspace ───────────────────────────────────────────────────────────
WORKDIR="$(mktemp -d)"
trap 'kill $SERVER_PID 2>/dev/null; rm -rf "$WORKDIR"' EXIT
echo ""
echo "=========================================="
echo " Submission Compliance Test"
echo "=========================================="
echo ""
info "Zip:     $ZIP_PATH"
info "Workdir: $WORKDIR"
echo ""

# ── 1. Extract ───────────────────────────────────────────────────────────────
echo "── 1. Extract zip ──"
unzip -q "$ZIP_PATH" -d "$WORKDIR"

# Find the project root (may be nested one level)
PROJECT_DIR=""
for candidate in "$WORKDIR" "$WORKDIR"/*/; do
  if [[ -f "${candidate}requirements.txt" ]]; then
    PROJECT_DIR="${candidate%/}"
    break
  fi
done

if [[ -z "$PROJECT_DIR" ]]; then
  fail "Could not find requirements.txt in extracted zip"
  echo ""; echo "Results: $PASSES passed, $FAILURES failed"; exit 1
fi
pass "Zip extracted, project root: $(basename "$PROJECT_DIR")"

# ── 2. "What to Submit" — required files ─────────────────────────────────────
echo ""
echo "── 2. Required files (What to Submit) ──"

# Source code
if [[ -d "$PROJECT_DIR/app" ]] && ls "$PROJECT_DIR/app/"*.py &>/dev/null; then
  pass "Working source code (app/ directory with .py files)"
else
  fail "Missing app/ directory with Python source files"
fi

# requirements.txt
if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
  pass "requirements.txt exists"
else
  fail "requirements.txt missing"
fi

# README.md
if [[ -f "$PROJECT_DIR/README.md" ]]; then
  pass "README.md exists"
else
  fail "README.md missing"
fi

# README content checks
if [[ -f "$PROJECT_DIR/README.md" ]]; then
  README="$(cat "$PROJECT_DIR/README.md")"

  # Step-by-step setup instructions
  if echo "$README" | grep -qi "pip install\|requirements"; then
    pass "README: contains setup/install instructions"
  else
    fail "README: missing setup/install instructions"
  fi

  # Model choice
  if echo "$README" | grep -qi "model\|llama\|llm"; then
    pass "README: mentions model choice"
  else
    fail "README: missing model choice explanation"
  fi

  # Repo content handling strategy
  if echo "$README" | grep -qi "tier\|priorit\|filter\|strateg\|content\|handling"; then
    pass "README: describes repo content handling strategy"
  else
    fail "README: missing repo content handling strategy"
  fi
fi

# No hardcoded API keys in source
echo ""
echo "── 3. Security check ──"

if grep -r "NEBIUS_API_KEY\s*=" "$PROJECT_DIR/app/" --include="*.py" | grep -v "os\.\|getenv\|environ\|config\.\|import" | grep -v "^#" | head -1 | grep -qv "getenv"; then
  # Double-check: look for string literals that look like keys
  if grep -rP '(v1\.[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})' "$PROJECT_DIR/app/" --include="*.py" 2>/dev/null; then
    fail "Possible hardcoded API key found in source code"
  else
    pass "No hardcoded API keys in source"
  fi
else
  pass "No hardcoded API keys in source"
fi

if [[ -f "$PROJECT_DIR/.env" ]]; then
  fail ".env file with real credentials included in submission!"
else
  pass "No .env file in submission (credentials not leaked)"
fi

if [[ -f "$PROJECT_DIR/.env.example" ]]; then
  pass ".env.example template provided"
else
  warn ".env.example not included (optional but recommended)"
fi

# ── 4. Install dependencies ──────────────────────────────────────────────────
echo ""
echo "── 4. Install dependencies ──"

python3 -m venv "$WORKDIR/venv"
source "$WORKDIR/venv/bin/activate"

if pip install -q -r "$PROJECT_DIR/requirements.txt" 2>"$WORKDIR/pip_errors.log"; then
  pass "pip install -r requirements.txt succeeded"
else
  fail "pip install failed (see $WORKDIR/pip_errors.log)"
  cat "$WORKDIR/pip_errors.log"
  echo ""; echo "Results: $PASSES passed, $FAILURES failed"; exit 1
fi

# ── 5. Start server (BLOCKING CRITERION) ─────────────────────────────────────
echo ""
echo "── 5. Start server (Blocking Criterion) ──"

PORT=18765  # use non-standard port to avoid conflicts
SERVER_PID=""

cd "$PROJECT_DIR"
NEBIUS_API_KEY="$NEBIUS_API_KEY" GITHUB_TOKEN="${GITHUB_TOKEN:-}" \
  uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
  >"$WORKDIR/server.log" 2>&1 &
SERVER_PID=$!

# Wait for server to be ready (up to 15 seconds)
SERVER_READY=false
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "" "http://127.0.0.1:$PORT/" 2>/dev/null || \
     curl -s -o /dev/null -w "" "http://127.0.0.1:$PORT/docs" 2>/dev/null; then
    SERVER_READY=true
    break
  fi
  sleep 0.5
done

if $SERVER_READY; then
  pass "Server started on port $PORT"
else
  fail "Server failed to start within 15s"
  echo "  Server log:"
  cat "$WORKDIR/server.log" | head -30
  echo ""; echo "Results: $PASSES passed, $FAILURES failed"; exit 1
fi

BASE="http://127.0.0.1:$PORT"

# ── 6. POST /summarize endpoint exists (BLOCKING CRITERION) ──────────────────
echo ""
echo "── 6. Endpoint & format tests ──"

# 6a. Valid repo — the exact curl from the task spec
info "Testing with psf/requests (from task spec)..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "$BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}' \
  --max-time 120)

BODY=$(echo "$RESPONSE" | sed '$d')
STATUS=$(echo "$RESPONSE" | tail -1)

if [[ "$STATUS" == "200" ]]; then
  pass "POST /summarize returns 200 for valid repo (Blocking Criterion)"
else
  fail "POST /summarize returned $STATUS instead of 200 (Blocking Criterion)"
  echo "  Response: $BODY"
fi

# 6b. Response format: { summary, technologies, structure }
if echo "$BODY" | jq -e '.summary' >/dev/null 2>&1; then
  pass "Response has 'summary' field (string)"
else
  fail "Response missing 'summary' field"
fi

if echo "$BODY" | jq -e '.technologies | if type == "array" then true else false end' >/dev/null 2>&1; then
  pass "Response has 'technologies' field (array)"
else
  fail "Response missing or wrong type for 'technologies' field"
fi

if echo "$BODY" | jq -e '.structure' >/dev/null 2>&1; then
  pass "Response has 'structure' field (string)"
else
  fail "Response missing 'structure' field"
fi

# 6c. Summary quality — basic sanity
SUMMARY_LEN=$(echo "$BODY" | jq -r '.summary' 2>/dev/null | wc -c)
if [[ "$SUMMARY_LEN" -gt 50 ]]; then
  pass "Summary is meaningful (${SUMMARY_LEN} chars)"
else
  fail "Summary seems too short (${SUMMARY_LEN} chars)"
fi

TECH_COUNT=$(echo "$BODY" | jq '.technologies | length' 2>/dev/null)
if [[ "$TECH_COUNT" -gt 0 ]]; then
  pass "Technologies list is non-empty ($TECH_COUNT items)"
  info "Technologies: $(echo "$BODY" | jq -r '.technologies | join(", ")')"
else
  fail "Technologies list is empty"
fi

# ── 7. Error responses ───────────────────────────────────────────────────────
echo ""
echo "── 7. Error handling ──"

# 7a. Invalid URL → 422
ERR_RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "$BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{"github_url": "not-a-url"}' \
  --max-time 15)
ERR_STATUS=$(echo "$ERR_RESPONSE" | tail -1)

if [[ "$ERR_STATUS" == "422" || "$ERR_STATUS" == "400" ]]; then
  pass "Invalid URL returns $ERR_STATUS"
else
  fail "Invalid URL returned $ERR_STATUS (expected 422 or 400)"
fi

# 7b. Missing field → 422
ERR_RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "$BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/psf/requests"}' \
  --max-time 15)
ERR_STATUS=$(echo "$ERR_RESPONSE" | tail -1)

if [[ "$ERR_STATUS" == "422" ]]; then
  pass "Missing github_url field returns 422"
else
  fail "Missing field returned $ERR_STATUS (expected 422)"
fi

# 7c. Nonexistent repo → error with { status, message }
info "Testing nonexistent repo..."
ERR_RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "$BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/nonexistent-user-abc123/nonexistent-repo-xyz789"}' \
  --max-time 30)
ERR_BODY=$(echo "$ERR_RESPONSE" | sed '$d')
ERR_STATUS=$(echo "$ERR_RESPONSE" | tail -1)

if [[ "$ERR_STATUS" -ge 400 && "$ERR_STATUS" -lt 600 ]]; then
  pass "Nonexistent repo returns error status $ERR_STATUS"
else
  fail "Nonexistent repo returned $ERR_STATUS (expected 4xx/5xx)"
fi

# Check error format: { "status": "error", "message": "..." }
# FastAPI wraps in "detail", so check both top-level and nested
HAS_ERROR_FORMAT=false
if echo "$ERR_BODY" | jq -e '.status == "error" and .message' >/dev/null 2>&1; then
  HAS_ERROR_FORMAT=true
elif echo "$ERR_BODY" | jq -e '.detail.status == "error" and .detail.message' >/dev/null 2>&1; then
  HAS_ERROR_FORMAT=true
elif echo "$ERR_BODY" | jq -e '.detail | type == "string"' >/dev/null 2>&1; then
  HAS_ERROR_FORMAT=true  # FastAPI default format
fi

if $HAS_ERROR_FORMAT; then
  pass "Error response has status/message format"
else
  warn "Error response format: $ERR_BODY"
fi

# 7d. Empty body → 422
ERR_RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "$BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{}' \
  --max-time 15)
ERR_STATUS=$(echo "$ERR_RESPONSE" | tail -1)

if [[ "$ERR_STATUS" == "422" ]]; then
  pass "Empty body returns 422"
else
  fail "Empty body returned $ERR_STATUS (expected 422)"
fi

# ── 8. Second repo test (different language) ─────────────────────────────────
echo ""
echo "── 8. Second repo test ──"

info "Testing with a small repo..."
RESPONSE2=$(curl -s -w "\n%{http_code}" \
  -X POST "$BASE/summarize" \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/keleshev/schema"}' \
  --max-time 120)
BODY2=$(echo "$RESPONSE2" | sed '$d')
STATUS2=$(echo "$RESPONSE2" | tail -1)

if [[ "$STATUS2" == "200" ]]; then
  pass "Second repo (keleshev/schema) returns 200"
  info "Summary: $(echo "$BODY2" | jq -r '.summary' | head -c 120)..."
else
  fail "Second repo returned $STATUS2"
fi

# ── Results ───────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo -e " Results: ${GREEN}$PASSES passed${NC}, ${RED}$FAILURES failed${NC}"
echo "=========================================="

if [[ "$FAILURES" -eq 0 ]]; then
  echo -e " ${GREEN}Submission is ready!${NC}"
  exit 0
else
  echo -e " ${RED}Fix the failures above before submitting.${NC}"
  exit 1
fi
