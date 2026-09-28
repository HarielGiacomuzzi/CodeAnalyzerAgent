"""End-to-end smoke test: analyze every file in samples/ against a running instance.

Usage: uv run python scripts/smoke.py [BASE_URL]   (default http://localhost:8000)
Exits 1 if the service is unhealthy or any analysis fails validation.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
SAMPLES = {
    "insecure_app.py": ("python", "security"),
    "slow_report.py": ("python", "performance"),
    "buggy_cart.js": ("auto", "general"),
    "clean_utils.py": ("python", "general"),
}
REQUIRED = {"language", "summary", "issues", "suggestions", "metrics", "analysis_type", "stats"}


def _parse(raw: bytes) -> dict:
    try:
        return json.loads(raw or b"{}")
    except ValueError:
        return {"detail": raw[:200].decode(errors="replace")}


def call(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as res:
            return res.status, _parse(res.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        return 0, {"detail": str(exc)}


def main() -> int:
    status, health = call("GET", "/health")
    print(f"GET /health -> {status} {health}")
    if status != 200:
        return 1

    failures = 0
    for name, (language, analysis_type) in SAMPLES.items():
        code = (Path(__file__).parent.parent / "samples" / name).read_text()
        status, body = call("POST", "/analyze", {"code": code, "language": language, "analysis_type": analysis_type})
        missing = REQUIRED - body.keys()
        if status != 200 or missing:
            failures += 1
            print(f"FAIL {name}: HTTP {status} detail={body.get('detail')} missing={sorted(missing)}")
            continue
        print(f"OK   {name} [{analysis_type}] language={body['language']} issues={len(body['issues'])} metrics={body['metrics']}")
        print(f"     summary: {body['summary']}")
        for issue in body["issues"]:
            print(f"     - {issue['severity']:<8} line {issue['line']}: [{issue['category']}] {issue['description']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
