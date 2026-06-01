"""FastAPI application with POST /summarize endpoint."""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.content_extractor import (
    ExtractedContent,
    build_prompt_content,
    build_tree_text,
    select_files,
)
from app.github_client import GitHubClient, GitHubClientError, parse_github_url
from app.llm_client import LLMClient
from app.models import ErrorResponse, SummarizeRequest, SummarizeResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GitHub Repository Summarizer", version="1.0.0")


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    """Summarize a public GitHub repository using LLM analysis."""
    gh = GitHubClient()
    llm = LLMClient()

    try:
        # 1. Parse URL
        owner, repo = parse_github_url(request.github_url)
        logger.info("Summarizing %s/%s", owner, repo)

        # 2. Fetch repo metadata
        repo_info = await gh.get_repo_info(owner, repo)
        default_branch = repo_info.get("default_branch", "main")

        # 3. Fetch content in parallel-friendly order
        readme = await gh.get_readme(owner, repo)
        languages = await gh.get_languages(owner, repo)
        tree = await gh.get_tree(owner, repo, default_branch)

        # 4. Build tree text and select files
        tree_text = build_tree_text(tree)
        tier1_paths, tier2_paths = select_files(tree)

        # 5. Fetch selected file contents
        tier1_files: dict[str, str] = {}
        for path in tier1_paths:
            try:
                tier1_files[path] = await gh.get_file_content(owner, repo, path)
            except GitHubClientError:
                logger.warning("Failed to fetch tier 1 file: %s", path)

        tier2_files: dict[str, str] = {}
        for path in tier2_paths:
            try:
                tier2_files[path] = await gh.get_file_content(owner, repo, path)
            except GitHubClientError:
                logger.warning("Failed to fetch tier 2 file: %s", path)

        # 6. Build prompt content
        content = ExtractedContent(
            readme=readme,
            tree_text=tree_text,
            languages=languages,
            tier1_files=tier1_files,
            tier2_files=tier2_files,
        )
        prompt_content = build_prompt_content(content)
        logger.info("Prompt content: %d chars (~%d tokens)", len(prompt_content), len(prompt_content) // 4)

        # 7. Call LLM
        result = await llm.summarize(request.github_url, prompt_content)

        return SummarizeResponse(**result)

    except GitHubClientError as e:
        logger.error("GitHub error: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=ErrorResponse(message=e.message).model_dump())

    except ValueError as e:
        logger.error("Validation/parsing error: %s", e)
        raise HTTPException(status_code=400, detail=ErrorResponse(message=str(e)).model_dump())

    except Exception as e:
        logger.exception("Unexpected error during summarization")
        raise HTTPException(status_code=502, detail=ErrorResponse(message=f"LLM service error: {e}").model_dump())

    finally:
        await gh.close()
