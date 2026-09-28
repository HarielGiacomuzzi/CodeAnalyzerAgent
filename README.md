# Code Analyzer Agent

A FastAPI service and web UI that analyzes source code with Claude (`claude-opus-5`) via a small tool-using agent and returns structured JSON: a summary, a severity-ranked list of issues, general suggestions, and quality metrics.

**Live demo:** _not deployed yet — see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)_

## Features

- `POST /analyze` with Pydantic request validation
- Three analysis types: general, security, performance
- Structured output enforced by a JSON schema (the LLM cannot return free text)
- Issues with severity, line number, category, description, and suggestion, sorted by severity
- Metrics (complexity, readability, test coverage estimate) plus deterministic line stats
- Agent tool `get_code_stats` gives the model objective size/nesting data before it judges the code
- Language auto-detection (`"language": "auto"`)
- Result caching for identical requests, reported via the `X-Cache` header
- `/health` endpoint
- Responsive web UI: paste or upload code, language and analysis-type selectors, loading state, colour-coded issues
- Railway-ready Docker image

## Quick start

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), and an Anthropic API key.

```bash
git clone git@github.com:HarielGiacomuzzi/CodeAnalyzerAgent.git
cd CodeAnalyzerAgent
uv sync
cp .env.example .env   # then put your key in .env
export $(grep -v '^#' .env | xargs)
uv run uvicorn main:app --reload
```

Open http://localhost:8000 for the UI; interactive API docs at http://localhost:8000/docs.

## Usage

```bash
curl -s http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import os\ndef run(cmd):\n    os.system(cmd)\n",
    "language": "python",
    "analysis_type": "security"
  }'
```

Illustrative response (the actual text depends on what the model finds):

```json
{
  "language": "python",
  "summary": "A three-line helper that shells out to run an arbitrary command. It has no input validation and passes attacker-controllable strings straight to the shell, which is a critical injection risk.",
  "issues": [
    {
      "severity": "critical",
      "line": 3,
      "category": "security",
      "description": "os.system(cmd) executes cmd through the shell, so any caller-supplied string can inject arbitrary shell commands.",
      "suggestion": "Use subprocess.run(shlex.split(cmd), shell=False) or, better, take an argument list instead of a raw string."
    },
    {
      "severity": "low",
      "line": null,
      "category": "maintainability",
      "description": "run() has no docstring or type hints, so callers can't tell what kind of input it expects.",
      "suggestion": "Add a docstring and a str type hint for cmd."
    }
  ],
  "suggestions": [
    "Add unit tests that assert shell metacharacters in cmd are never passed to a shell.",
    "Validate or allow-list the commands this function is permitted to run."
  ],
  "metrics": {
    "complexity": "low",
    "readability": "fair",
    "test_coverage_estimate": "none"
  },
  "analysis_type": "security",
  "stats": {
    "total_lines": 3,
    "code_lines": 3,
    "blank_lines": 0,
    "comment_lines": 0,
    "max_line_length": 18,
    "max_indent_depth": 1
  }
}
```

Request fields:

| Field | Required | Notes |
|---|---|---|
| `code` | yes | 1-100000 characters |
| `language` | no | default `auto`; free-form string, lower-cased |
| `analysis_type` | no | `general`, `security`, or `performance`; default `general` |

Full schema and error responses: [docs/API.md](docs/API.md).

## Web interface

Paste code into the text area, or use "Upload file" to load it from disk — the language selector is auto-set from the file extension (falling back to "Auto-detect" for unrecognised extensions). Pick an analysis type, then click "Analyze" or press Ctrl+Enter (Cmd+Enter on macOS). While the request is in flight the button shows a spinner and is disabled. When the response comes back, the results panel renders a summary with language/analysis-type/issue-count chips, a metrics grid, the issues list, and general suggestions. Issues are colour-coded by severity: critical red, high orange, medium yellow, low green, info blue.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(none)_ | Required. Anthropic API key used by the analyzer. Without it, `/analyze` returns 503. |
| `ANTHROPIC_MODEL` | `claude-opus-5` | Claude model id to use. |
| `PORT` | `8000` | Port the server listens on inside the container; Railway sets this automatically. |

## Testing

```bash
uv run pytest
```

Unit tests cover: request/response models and validation (`tests/test_models.py`), the deterministic line-stats helper (`tests/test_stats.py`), the agent tool-use loop against a fake Claude client (`tests/test_llm.py`), the `/analyze` and `/health` endpoints including error mapping and caching (`tests/test_api.py`), and static-frontend serving plus an XSS-safety check on `app.js` (`tests/test_frontend.py`).

Smoke test against a running instance:

```bash
uv run python scripts/smoke.py [BASE_URL]   # default http://localhost:8000
```

It checks `/health`, then posts every file in `samples/` to `/analyze` and verifies the response has all required fields. Run it against a live server with a real `ANTHROPIC_API_KEY` set to capture an example run.

## Deployment

Deploys to Railway from the included `Dockerfile`: connect the GitHub repo (or run `railway up`), set the `ANTHROPIC_API_KEY` variable, Railway health-checks `/health` per `railway.json`, then generate a public domain. Full steps, CLI option, and troubleshooting: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Project structure

```
main.py                FastAPI app: routes, caching, error mapping, static mount
analyzer/
  models.py             Pydantic request/response/schema models
  stats.py              Deterministic line/comment/indent stats (also the get_code_stats tool)
  prompts.py             System prompt and user-message builder
  llm.py                 CodeAnalyzer protocol and the Anthropic tool-use agent loop
static/
  index.html             Web UI markup
  app.js                 Web UI logic (fetch, render, file upload)
  styles.css             Web UI styling, incl. severity colours
tests/                   pytest suite (models, stats, llm, api, frontend)
samples/                 Sample code files used by scripts/smoke.py
scripts/
  smoke.py               End-to-end smoke test against a running instance
docs/                    API, architecture, prompts, and deployment reference
Dockerfile               Container image used for local runs and Railway
railway.json             Railway build/deploy config (health check, restart policy)
.env.example             Environment variable template
requirements.md          Original lab assignment/requirements
```

## Documentation

- [docs/API.md](docs/API.md) — endpoint and schema reference
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — request flow, module responsibilities, design decisions
- [docs/PROMPTS.md](docs/PROMPTS.md) — system prompt design and how to add an analysis type
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — Railway deployment and troubleshooting

## Requirements checklist

| Requirement | Implemented in |
|---|---|
| `POST /analyze` accepting code + language | `main.py` (`analyze`), `analyzer/models.py` (`AnalyzeRequest`) |
| System prompt instructing the LLM how to analyze code | `analyzer/prompts.py` (`BASE_SYSTEM_PROMPT`, `FOCUS`) |
| Structured JSON output: summary | `analyzer/models.py` (`AnalysisResult.summary`) |
| Structured JSON output: issues (severity, line, category, description, suggestion) | `analyzer/models.py` (`Issue`) |
| Structured JSON output: suggestions | `analyzer/models.py` (`AnalysisResult.suggestions`) |
| Structured JSON output: metrics (complexity, readability, test coverage estimate) | `analyzer/models.py` (`Metrics`) |
| Data validation using Pydantic | `analyzer/models.py` (all models) |
| LLM client abstraction (at least one provider) | `analyzer/llm.py` (`CodeAnalyzer` protocol, `AnthropicAnalyzer`) |
| Health check endpoint | `main.py` (`GET /health`) |
| Web interface: paste or upload code | `static/index.html`, `static/app.js` |
| Web interface: language selector dropdown | `static/index.html` (`#language`) |
| Web interface: Analyze button with loading state | `static/index.html` (`#analyze-btn`), `static/app.js` (`setLoading`) |
| Web interface: results panel (summary, issues, suggestions, metrics) | `static/app.js` (`render`) |
| Responsive design | `static/styles.css` |
| At least 2 analysis types | `analyzer/models.py` (`AnalysisType`: general, security, performance) |
| Tested with sample code | `samples/`, `scripts/smoke.py`, `tests/` |
| Deployed to Railway | See "Live demo" at the top of this README |
| Extension — Language Detection | Done: `"language": "auto"` (`analyzer/models.py`, `analyzer/prompts.py`) |
| Extension — Caching | Done: `X-Cache` header (`main.py`) |
| Extension — Multi-file analysis | Not implemented |
| Extension — Diff analysis | Not implemented |

## License

See [LICENSE](LICENSE) (Apache License 2.0).
