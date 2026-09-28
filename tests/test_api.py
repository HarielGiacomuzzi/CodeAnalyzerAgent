import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

import main
from analyzer.llm import AnalysisError
from analyzer.models import AnalysisResult, Issue, Metrics

RESULT = AnalysisResult(
    language="python",
    summary="Adds numbers. Fine.",
    issues=[
        Issue(severity="low", line=1, category="style", description="d", suggestion="s"),
        Issue(severity="high", line=99, category="bug", description="d", suggestion="s"),
    ],
    suggestions=["Add tests"],
    metrics=Metrics(complexity="low", readability="good", test_coverage_estimate="none"),
)


class FakeAnalyzer:
    model = "fake-model"

    def __init__(self, result=RESULT, error=None):
        self.result, self.error, self.calls = result, error, 0

    def analyze(self, code, language, analysis_type):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def client():
    main.CACHE.clear()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def use(analyzer):
    main.app.dependency_overrides[main.get_analyzer] = lambda: analyzer
    return analyzer


def test_health_reports_config(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is False
    assert body["model"]


def test_analyze_returns_structured_result(client):
    use(FakeAnalyzer())
    r = client.post("/analyze", json={"code": "a = 1 + 2\n", "language": "python", "analysis_type": "security"})
    assert r.status_code == 200
    body = r.json()
    assert r.headers["X-Cache"] == "MISS"
    assert body["analysis_type"] == "security"
    assert body["stats"]["total_lines"] == 1
    assert [i["severity"] for i in body["issues"]] == ["high", "low"]
    assert body["issues"][0]["line"] is None  # 99 is outside the 1-line file
    assert set(body["metrics"]) == {"complexity", "readability", "test_coverage_estimate"}


def test_identical_request_is_cached(client):
    fake = use(FakeAnalyzer())
    payload = {"code": "x = 1", "language": "python"}
    client.post("/analyze", json=payload)
    second = client.post("/analyze", json=payload)
    assert second.headers["X-Cache"] == "HIT"
    assert fake.calls == 1
    client.post("/analyze", json={**payload, "analysis_type": "performance"})
    assert fake.calls == 2


@pytest.mark.parametrize("payload", [{}, {"code": "   "}, {"code": "x", "analysis_type": "nope"}, {"code": "x", "language": "a\nb"}])
def test_invalid_input_is_422_and_skips_llm(client, payload):
    fake = use(FakeAnalyzer())
    assert client.post("/analyze", json=payload).status_code == 422
    assert fake.calls == 0


def test_missing_api_key_is_503(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    main.get_anthropic_analyzer.cache_clear()
    r = client.post("/analyze", json={"code": "x = 1"})
    assert r.status_code == 503
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def _status_error(cls, status):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


@pytest.mark.parametrize(
    "error,status",
    [
        (AnalysisError("LLM returned malformed analysis JSON"), 502),
        (_status_error(anthropic.RateLimitError, 429), 429),
        (_status_error(anthropic.InternalServerError, 500), 502),
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")), 502),
    ],
)
def test_llm_failures_map_to_clean_errors(client, error, status):
    use(FakeAnalyzer(error=error))
    r = client.post("/analyze", json={"code": "x = 1"})
    assert r.status_code == status
    assert r.json()["detail"]
