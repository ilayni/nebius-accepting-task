"""Nebius Token Factory LLM integration via OpenAI-compatible SDK."""

import json
import logging

from openai import AsyncOpenAI

from app.config import NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a code repository analyst. Analyze the provided repository content and return a JSON object with exactly these three fields:

- "summary": A 2-4 sentence description of what this project does, its purpose, and key features.
- "technologies": An array of programming languages, frameworks, libraries, and tools used in the project.
- "structure": A 2-3 sentence description of how the project is organized (directories, modules, key files).

Respond ONLY with valid JSON. No markdown formatting, no code fences, no extra text."""


class LLMClient:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=NEBIUS_API_KEY,
            base_url=NEBIUS_BASE_URL,
        )

    async def summarize(self, repo_url: str, content: str) -> dict:
        """Send repo content to LLM and parse the structured response.

        Returns:
            dict with keys: summary, technologies, structure
        """
        user_prompt = f"Analyze this GitHub repository: {repo_url}\n\n{content}"

        response = await self.client.chat.completions.create(
            model=NEBIUS_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        return _parse_llm_response(raw)


def _parse_llm_response(raw: str) -> dict:
    """Parse the LLM's JSON response, handling common formatting issues."""
    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s\nRaw: %s", e, raw[:500])
        raise ValueError(f"LLM returned invalid JSON: {e}") from e

    # Validate required fields
    if "summary" not in data or "technologies" not in data or "structure" not in data:
        missing = [f for f in ("summary", "technologies", "structure") if f not in data]
        raise ValueError(f"LLM response missing fields: {missing}")

    # Ensure technologies is a list
    if isinstance(data["technologies"], str):
        data["technologies"] = [t.strip() for t in data["technologies"].split(",")]

    return {
        "summary": str(data["summary"]),
        "technologies": list(data["technologies"]),
        "structure": str(data["structure"]),
    }
