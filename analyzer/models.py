from typing import Literal

from pydantic import BaseModel, Field, field_validator

AnalysisType = Literal["general", "security", "performance"]
Severity = Literal["critical", "high", "medium", "low", "info"]
Category = Literal["bug", "security", "performance", "style", "maintainability"]

MAX_CODE_CHARS = 100_000
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class AnalyzeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=MAX_CODE_CHARS, description="Source code to analyze")
    language: str = Field(
        default="auto",
        max_length=32,
        pattern=r"^\s*[A-Za-z0-9+#._-]+\s*$",
        description="Programming language, or 'auto' to let the model detect it",
    )
    analysis_type: AnalysisType = "general"

    @field_validator("code")
    @classmethod
    def code_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("code must not be blank")
        return v

    @field_validator("language")
    @classmethod
    def normalise_language(cls, v: str) -> str:
        return v.strip().lower()


class Issue(BaseModel):
    severity: Severity
    line: int | None = Field(description="1-based line number from the numbered listing, or null if the issue is file-wide")
    category: Category
    description: str = Field(description="What is wrong and why it matters")
    suggestion: str = Field(description="Concrete fix for this issue")


class Metrics(BaseModel):
    complexity: Literal["low", "medium", "high"]
    readability: Literal["poor", "fair", "good", "excellent"]
    test_coverage_estimate: Literal["none", "low", "medium", "high"] = Field(
        description="How much of this code is plausibly covered by tests, judged from the code itself"
    )


class AnalysisResult(BaseModel):
    """Exactly what the LLM must return (used as the structured-output schema)."""

    language: str = Field(description="Programming language of the code (detected when the request said 'auto')")
    summary: str = Field(description="2-3 sentence overview of the code and its overall quality")
    issues: list[Issue]
    suggestions: list[str] = Field(description="General improvements not tied to a single line")
    metrics: Metrics


class CodeStats(BaseModel):
    total_lines: int
    code_lines: int
    blank_lines: int
    comment_lines: int
    max_line_length: int
    max_indent_depth: int


class AnalyzeResponse(AnalysisResult):
    analysis_type: AnalysisType
    stats: CodeStats

    @classmethod
    def build(cls, result: AnalysisResult, analysis_type: AnalysisType, stats: CodeStats) -> "AnalyzeResponse":
        issues = [
            i if i.line is None or 1 <= i.line <= stats.total_lines else i.model_copy(update={"line": None})
            for i in result.issues
        ]
        issues.sort(key=lambda i: SEVERITY_ORDER[i.severity])
        return cls(**result.model_dump(exclude={"issues"}), issues=issues, analysis_type=analysis_type, stats=stats)
