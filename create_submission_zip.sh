#!/usr/bin/env bash
# =============================================================================
# create_submission_zip.sh — Package nebius-repo-summarizer for submission
#
# Creates a clean zip excluding .env, API keys, venv, caches, and internal docs.
#
# Usage (from the nebius/ folder):
#   ./create_submission_zip.sh
#
# Output: ./nebius-repo-summarizer.zip
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/nebius-repo-summarizer"
FOLDER_NAME="nebius-repo-summarizer"
ZIP_NAME="nebius-repo-summarizer.zip"
ZIP_PATH="$SCRIPT_DIR/$ZIP_NAME"
TEMP_DIR="$(mktemp -d)"

trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Packaging submission..."

rsync -a \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.mypy_cache' \
  --exclude='*.pyc' \
  --exclude='*.egg-info' \
  --exclude='dist' \
  --exclude='build' \
  --exclude='.git' \
  --exclude='arch.md' \
  "$SOURCE_DIR/" "$TEMP_DIR/$FOLDER_NAME/"

# Safety: verify no .env leaked in
if [[ -f "$TEMP_DIR/$FOLDER_NAME/.env" ]]; then
  echo "ERROR: .env file found in package — aborting!"
  exit 1
fi

# Safety: scan for hardcoded keys
if grep -rP '(v1\.[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9]{20,})' \
    "$TEMP_DIR/$FOLDER_NAME/" 2>/dev/null; then
  echo "ERROR: Possible API key found in source — aborting!"
  exit 1
fi

rm -f "$ZIP_PATH"
(cd "$TEMP_DIR" && zip -r "$ZIP_PATH" "$FOLDER_NAME/")

echo ""
echo "Created: $ZIP_PATH"
echo ""
echo "Contents:"
unzip -l "$ZIP_PATH" | tail -n +4 | head -n -2 | awk '{print $4}'
