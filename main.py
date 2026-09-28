import hashlib
import json
import os
import threading
from functools import lru_cache
from pathlib import Path

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles

from analyzer.llm import DEFAULT_MODEL, AnalysisError, AnthropicAnalyzer, CodeAnalyzer
from analyzer.models import AnalyzeRequest, AnalyzeResponse
from analyzer.stats import code_stats

app = FastAPI(
    title="Code Analyzer Agent",
    description="Analyze source code with Claude and get structured feedback.",
    version="0.1.0",
)

# ponytail: in-process FIFO cache, lost on restart and not shared across replicas; use Redis if that matters
CACHE: dict[str, AnalyzeResponse] = {}
CACHE_SIZE = 256
CACHE_LOCK = threading.Lock()


@lru_cache
def get_anthropic_analyzer() -> AnthropicAnalyzer:
    return AnthropicAnalyzer()


def get_analyzer() -> CodeAnalyzer:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "LLM not configured: set the ANTHROPIC_API_KEY environment variable")
    return get_anthropic_analyzer()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        "llm_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, response: Response, analyzer: CodeAnalyzer = Depends(get_analyzer)) -> AnalyzeResponse:
    key = hashlib.sha256(
        json.dumps([analyzer.model, req.analysis_type, req.language, req.code]).encode()
    ).hexdigest()
    if key in CACHE:
        response.headers["X-Cache"] = "HIT"
        return CACHE[key]

    try:
        result = analyzer.analyze(req.code, req.language, req.analysis_type)
    except AnalysisError as exc:
        raise HTTPException(502, str(exc)) from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(429, "LLM provider rate limit reached, retry shortly") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(502, f"LLM provider error (HTTP {exc.status_code})") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(502, "Could not reach the LLM provider") from exc

    result = AnalyzeResponse.build(result, req.analysis_type, code_stats(req.code))
    with CACHE_LOCK:
        if len(CACHE) >= CACHE_SIZE:
            CACHE.pop(next(iter(CACHE)), None)
        CACHE[key] = result
    response.headers["X-Cache"] = "MISS"
    return result


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
