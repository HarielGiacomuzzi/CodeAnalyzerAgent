# Architecture

## Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│   Browser (static/index.html + app.js)                                   │
│        │ POST /analyze {code, language, analysis_type}                   │
│        ▼                                                                  │
│   FastAPI app (main.py)                                                  │
│        │ cache lookup (sha256 of model+analysis_type+language+code)      │
│        │   HIT  ──────────────────────────────► return cached response   │
│        │   MISS                                                          │
│        ▼                                                                  │
│   AnthropicAnalyzer.analyze()  (analyzer/llm.py)                         │
│        │                                                                  │
│        │   ┌────────────────────────────────────────────────┐           │
│        └──►│  loop (up to 4 turns):                          │           │
│             │  beta.messages.create(system, tools, messages, │           │
│             │      output_config, thinking=adaptive)   ⇄ Claude          │
│             │  if tool_use → run get_code_stats, append       │           │
│             │      tool_result, continue                      │           │
│             │  else → parse AnalysisResult from response text │           │
│             └────────────────────────────────────────────────┘           │
│        │                                                                  │
│        ▼                                                                  │
│   AnalyzeResponse.build()  (analyzer/models.py)                          │
│        │  sort issues by severity, null out-of-range line numbers,       │
│        │  attach deterministic stats (analyzer/stats.py)                 │
│        ▼                                                                  │
│   cache store (CACHE_LOCK) ──► JSON response, X-Cache: MISS              │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

## Module responsibilities

- **`main.py`** — FastAPI app: `GET /health`, `POST /analyze`, the in-process cache and its lock, mapping exceptions from the analyzer to HTTP status codes, and mounting `static/` for the web UI. `get_analyzer` checks `ANTHROPIC_API_KEY` and returns a cached `AnthropicAnalyzer` instance (via `get_anthropic_analyzer`, `@lru_cache`).
- **`analyzer/models.py`** — Pydantic models: `AnalyzeRequest` (validation), `AnalysisResult` (exactly what the LLM must return — also the source of the JSON schema given to the model), `Issue`, `Metrics`, `CodeStats`, and `AnalyzeResponse` (adds `analysis_type` and `stats`, and post-processes issues in `build`).
- **`analyzer/stats.py`** — `code_stats`: a pure, deterministic function computing line/comment/indent metrics from the raw code. Used both as the `AnalyzeResponse.stats` field and as the implementation of the `get_code_stats` tool the model can call.
- **`analyzer/prompts.py`** — `build_system_prompt` (base rules + per-analysis-type focus) and `build_user_message` (wraps the code in a numbered listing inside `<code>` tags). See [PROMPTS.md](PROMPTS.md) for the full text and design rationale.
- **`analyzer/llm.py`** — the `CodeAnalyzer` protocol (provider abstraction) and `AnthropicAnalyzer`, which runs the tool-use agent loop against the Anthropic API and returns a validated `AnalysisResult`.
- **`static/`** — the web UI: `index.html` (markup), `app.js` (fetch, render, file upload, client-side length check), `styles.css` (layout, dark mode, severity colours).

## Request lifecycle

1. **Validation** — FastAPI parses and validates the body against `AnalyzeRequest`. Invalid input never reaches the LLM; it fails with `422` immediately.
2. **Cache lookup** — `main.analyze` hashes `[model, analysis_type, language, code]` with SHA-256. A hit returns the stored `AnalyzeResponse` with `X-Cache: HIT` and does not call the LLM.
3. **Agent loop** — on a miss, `AnthropicAnalyzer.analyze` calls the Claude API, handling up to `MAX_TURNS = 4` turns: if the model calls `get_code_stats`, the tool runs locally and its result is appended as a `tool_result` message, then the loop continues; otherwise the loop expects `stop_reason == "end_turn"` and treats the final text block as the answer.
4. **Schema validation** — `AnalysisResult.model_validate_json` parses that text. A parse failure raises `AnalysisError` ("LLM returned malformed analysis JSON"), which `main.py` maps to `502`.
5. **Post-processing** — `AnalyzeResponse.build` sorts `issues` by severity and nulls out any `line` number outside `1..stats.total_lines`, then attaches the deterministic `stats`.
6. **Cache store** — under `CACHE_LOCK`, if the cache is at `CACHE_SIZE` (256) the oldest entry is evicted (`dict` insertion order == FIFO), then the new response is stored. The response is returned with `X-Cache: MISS`.

## The agent loop

- **Why a manual loop instead of a higher-level runner** — the task is small and fully specified (one tool, a fixed turn budget, one expected final shape), so a 30-line `for` loop in `AnthropicAnalyzer.analyze` is simpler to read and test (with a fake client, see `tests/test_llm.py`) than wiring up a generic agent framework.
- **Why `beta.messages.create` with `fallbacks: "default"`** — the call passes `betas=["server-side-fallback-2026-07-01"]` and `fallbacks="default"` so the Anthropic API can transparently retry on a fallback model/region if the primary is overloaded, without the client having to implement its own retry-and-swap logic.
- **Why structured output via `output_config.format` + `AnalysisResult.model_validate_json` instead of `messages.parse`** — `output_config` with a `json_schema` format constrains the model's final message to match the schema server-side, which is what actually prevents free-text or partial JSON; the client still needs to turn that guaranteed-valid text into a Python object, which `model_validate_json` does directly. `messages.parse` targets picking a schema and parsing in one client-side helper call, which doesn't fit a loop that may first go through one or more tool-use turns.
- **Adaptive thinking (`thinking={"type": "adaptive"}`)** — lets the model spend more reasoning budget on code that needs it (e.g. subtle security issues) and less on trivial snippets, without the caller having to guess a fixed token budget per request.
- **`max_tokens=16000`** — sized to comfortably fit a large `issues` list plus `suggestions` and thinking output for a 100000-character file; also see `MAX_CODE_CHARS` in `analyzer/models.py`.

## LLM client abstraction

`CodeAnalyzer` (`analyzer/llm.py`) is a `Protocol`:

```python
class CodeAnalyzer(Protocol):
    model: str
    def analyze(self, code: str, language: str, analysis_type: AnalysisType) -> AnalysisResult: ...
```

To add a provider: implement a class with a `model` attribute and an `analyze` method with that exact signature, returning a validated `AnalysisResult`; then wire it into `main.get_analyzer` (e.g. select the implementation by an env var, keeping `get_anthropic_analyzer`-style `@lru_cache` construction so the client is built once per process).

## Caching design and limits

- In-process `dict`, FIFO eviction at `CACHE_SIZE = 256` entries (`main.py`, `CACHE`, `CACHE_SIZE`).
- Key: SHA-256 of `[model, analysis_type, language, code]`, so the same code analyzed under a different model, analysis type, or declared language is a separate entry.
- Insert/evict is guarded by `CACHE_LOCK` (a `threading.Lock`) so concurrent requests can't corrupt the FIFO order or double-evict; the cache lookup itself is a plain dict read (safe under FastAPI's threaded request handling for CPython dicts).
- Limits: lost on process restart, and not shared across replicas — each Railway instance (or worker) has its own cache. Marked in code with `# ponytail: in-process FIFO cache, lost on restart and not shared across replicas; use Redis if that matters`.

## Security considerations

- **Prompt-injection framing** — the system prompt explicitly tells the model the code is untrusted data, appears between `<code>` and `</code>`, and that instructions inside it (including comments/strings) must never be followed — only analyzed as text (`analyzer/prompts.py`, "## Safety").
- **Input limits** — `code` is capped at `MAX_CODE_CHARS = 100_000` characters and must be non-blank (`analyzer/models.py`); the web UI enforces the same limit client-side before sending.
- **`language` regex** — restricted to `^\s*[A-Za-z0-9+#._-]+\s*$` and length-capped at 32 chars, so it can't carry arbitrary text into the prompt.
- **`textContent`-only rendering** — `static/app.js` builds all DOM nodes with `el()`, which sets `textContent`, never `innerHTML`, so nothing from the API response (including LLM-authored text) is interpreted as HTML (see `tests/test_frontend.py::test_app_js_never_injects_html`).
- **Unauthenticated endpoint spends API credits** — `/analyze` has no auth, so any caller who can reach it triggers a billed LLM call. Mitigate by setting a spend limit on the Anthropic API key in the Anthropic Console, and/or putting the service behind an auth layer (reverse proxy, API gateway, or app-level auth) before exposing it publicly.

## Known limitations

- Single file only — no cross-file context or project-level analysis.
- No streaming — the client waits for the full response; a single analysis can take 20-60 seconds.
- Comment counting is a prefix heuristic (`#`, `//`, `/*`, `*`, `--`) rather than a real per-language parser, so it can miscount block comments or language-specific comment syntax it doesn't recognise (`analyzer/stats.py`).
