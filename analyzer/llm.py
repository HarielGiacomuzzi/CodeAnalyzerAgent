import os
from typing import Protocol

import anthropic
from pydantic import ValidationError

from analyzer.models import AnalysisResult, AnalysisType
from analyzer.prompts import build_system_prompt, build_user_message
from analyzer.stats import code_stats

DEFAULT_MODEL = "claude-opus-5"
MAX_TURNS = 4

STATS_TOOL = {
    "name": "get_code_stats",
    "description": (
        "Returns objective metrics for the file under review: total/code/blank/comment line counts, "
        "longest line and maximum indentation depth. Takes no arguments. Call it once before judging complexity."
    ),
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
}

OUTPUT_FORMAT = {"type": "json_schema", "schema": anthropic.transform_schema(AnalysisResult.model_json_schema())}


class AnalysisError(Exception):
    """The LLM did not produce a usable analysis."""


class CodeAnalyzer(Protocol):
    """LLM client abstraction. Add a provider by implementing this and wiring it in main.get_analyzer."""

    model: str

    def analyze(self, code: str, language: str, analysis_type: AnalysisType) -> AnalysisResult: ...


class AnthropicAnalyzer:
    def __init__(self, client=None, model: str | None = None):
        self.client = client or anthropic.Anthropic()
        self.model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    def analyze(self, code: str, language: str, analysis_type: AnalysisType) -> AnalysisResult:
        messages = [{"role": "user", "content": build_user_message(code, language)}]
        for _ in range(MAX_TURNS):
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=build_system_prompt(analysis_type),
                tools=[STATS_TOOL],
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"format": OUTPUT_FORMAT},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": block.id, "content": self._run_tool(block.name, code)}
                    for block in response.content
                    if block.type == "tool_use"
                ]})
                continue
            if response.stop_reason != "end_turn":
                raise AnalysisError(f"LLM stopped without a result (stop_reason={response.stop_reason})")
            texts = [block.text for block in response.content if block.type == "text"]
            try:
                return AnalysisResult.model_validate_json(texts[-1] if texts else "")
            except ValidationError as exc:
                raise AnalysisError("LLM returned malformed analysis JSON") from exc
        raise AnalysisError("LLM did not finish within the tool-call limit")

    @staticmethod
    def _run_tool(name: str, code: str) -> str:
        if name == "get_code_stats":
            return code_stats(code).model_dump_json()
        return f"Unknown tool: {name}"
