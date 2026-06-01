"""Configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Required ---
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")
if not NEBIUS_API_KEY:
    raise RuntimeError("NEBIUS_API_KEY environment variable is required. See .env.example")

# --- Optional ---
GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")

# --- Nebius LLM ---
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
NEBIUS_MODEL = "meta-llama/Llama-3.3-70B-Instruct"

# --- Limits ---
MAX_FILE_SIZE = 100_000       # 100 KB per file
MAX_TREE_LINES = 100          # max lines in directory tree output
TOKEN_BUDGET = 12_000         # approximate token budget for repo content
CHARS_PER_TOKEN = 4           # rough char-to-token ratio
MAX_CONTENT_CHARS = TOKEN_BUDGET * CHARS_PER_TOKEN  # ~48,000 chars
