# API Reference

## Base URL

- Local: `http://localhost:8000`
- Deployed: not deployed yet — see [DEPLOYMENT.md](DEPLOYMENT.md)

Interactive OpenAPI docs are always live at `/docs` (Swagger UI) and `/openapi.json` (raw schema).

## `GET /health`

No parameters. Always returns `200`.

```json
{
  "status": "ok",
  "model": "claude-opus-5",
  "llm_configured": true
}
```

| Field | Meaning |
|---|---|
| `status` | Always `"ok"` if the process is up. |
| `model` | The Claude model id in use (`ANTHROPIC_MODEL`, default `claude-opus-5`). |
| `llm_configured` | `true` if `ANTHROPIC_API_KEY` is set. If `false`, `POST /analyze` will return `503`. |

## `POST /analyze`

### Request

| Field | Type | Required | Constraints | Default |
|---|---|---|---|---|
| `code` | string | yes | 1-100000 characters, must not be blank after stripping | — |
| `language` | string | no | max 32 chars, pattern `^\s*[A-Za-z0-9+#._-]+\s*$`, lower-cased | `"auto"` |
| `analysis_type` | string | no | one of `general`, `security`, `performance` | `"general"` |

```bash
curl -s http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"code": "print(1)", "language": "python", "analysis_type": "general"}'
```

### Response — `200`

Body is `AnalyzeResponse` (`analyzer/models.py`):

| Field | Type | Notes |
|---|---|---|
| `language` | string | Language of the code; detected by the model when the request said `"auto"`. |
| `summary` | string | 2-3 sentence overview and overall quality verdict. |
| `issues` | array of `Issue` | Sorted by severity: `critical`, `high`, `medium`, `low`, `info`. |
| `suggestions` | array of string | General improvements not tied to a single line. |
| `metrics` | `Metrics` | See below. |
| `analysis_type` | string | Echoes the request's `analysis_type`. |
| `stats` | `CodeStats` | Deterministic line stats, computed server-side (not by the LLM). |

`Issue`:

| Field | Type | Notes |
|---|---|---|
| `severity` | enum | `critical` \| `high` \| `medium` \| `low` \| `info` |
| `line` | integer or null | 1-based line number from the numbered listing shown to the model. `null` if file-wide, or if the model returned a line number outside the file's line range (`main.py`/`analyzer/models.py` `AnalyzeResponse.build` nulls those out). |
| `category` | enum | `bug` \| `security` \| `performance` \| `style` \| `maintainability` |
| `description` | string | What is wrong and why it matters. |
| `suggestion` | string | Concrete fix. |

`Metrics`:

| Field | Type | Notes |
|---|---|---|
| `complexity` | enum | `low` \| `medium` \| `high` |
| `readability` | enum | `poor` \| `fair` \| `good` \| `excellent` |
| `test_coverage_estimate` | enum | `none` \| `low` \| `medium` \| `high` — a judgment call by the model based only on what it sees in the file. |

`CodeStats` (all deterministic, computed from `code` by `analyzer/stats.py`, independent of the LLM):

| Field | Type | Notes |
|---|---|---|
| `total_lines` | integer | Total line count, including blank lines. |
| `code_lines` | integer | Non-blank, non-comment lines. |
| `blank_lines` | integer | Lines that are empty or whitespace-only. |
| `comment_lines` | integer | Non-blank lines starting with `#`, `//`, `/*`, `*`, or `--`. |
| `max_line_length` | integer | Length of the longest line. |
| `max_indent_depth` | integer | Deepest indentation, in units of 4 spaces (tabs expanded to 4 spaces). |

### Response header

`X-Cache: HIT` or `X-Cache: MISS`. Identical requests (same model, `analysis_type`, `language`, and `code`) hit an in-process cache and skip the LLM call. See [ARCHITECTURE.md](ARCHITECTURE.md#caching-design-and-limits) for how the cache is keyed and its limits.

### Example: full response (illustrative)

```json
{
  "language": "python",
  "summary": "A one-line script that prints a constant. It is correct and has no issues.",
  "issues": [],
  "suggestions": [
    "None — the code is too small to warrant structural suggestions."
  ],
  "metrics": {
    "complexity": "low",
    "readability": "good",
    "test_coverage_estimate": "none"
  },
  "analysis_type": "general",
  "stats": {
    "total_lines": 1,
    "code_lines": 1,
    "blank_lines": 0,
    "comment_lines": 0,
    "max_line_length": 8,
    "max_indent_depth": 0
  }
}
```

### Examples by analysis type

General:

```bash
curl -s http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"code": "def add(a, b):\n    return a + b\n", "language": "python", "analysis_type": "general"}'
```

Security:

```bash
curl -s http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"code": "import os\ndef run(cmd):\n    os.system(cmd)\n", "language": "python", "analysis_type": "security"}'
```

Performance:

```bash
curl -s http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"code": "def contains(items, target):\n    for a in items:\n        for b in items:\n            if a == b == target:\n                return True\n    return False\n", "language": "python", "analysis_type": "performance"}'
```

## Post-processing rules

Applied server-side to whatever the LLM returns, in `AnalyzeResponse.build` (`analyzer/models.py`):

- `issues` are sorted by severity (`critical` first, `info` last).
- Any `line` number outside `1..stats.total_lines` is replaced with `null`.

## Errors

| Status | Cause | Example `detail` |
|---|---|---|
| `422` | Request body fails Pydantic validation. | Standard FastAPI validation error array, e.g. for `{"code": ""}`: `[{"type": "value_error", "loc": ["body", "code"], "msg": "Value error, code must not be blank", ...}]` |
| `503` | `ANTHROPIC_API_KEY` is not set. | `"LLM not configured: set the ANTHROPIC_API_KEY environment variable"` |
| `429` | The Anthropic API returned a rate-limit error. | `"LLM provider rate limit reached, retry shortly"` |
| `502` | The LLM produced malformed/unusable output, refused, or the provider/network failed. | `"LLM returned malformed analysis JSON"`, `"LLM stopped without a result (stop_reason=...)"`, `"LLM did not finish within the tool-call limit"`, `"LLM provider error (HTTP 500)"`, `"Could not reach the LLM provider"`, `"LLM provider error"` |

Example `422` request/response:

```bash
curl -s http://localhost:8000/analyze -H "Content-Type: application/json" -d '{"code": ""}'
```

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "code"],
      "msg": "Value error, code must not be blank",
      "input": ""
    }
  ]
}
```
