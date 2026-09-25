"""Dataclass representing the result of an LLM-based mail analysis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    """Structured result parsed from the Ollama JSON response."""

    category: str
    importance_score: int
    sentiment: str
    summary: str
    recommended_action: str
    keywords: list[str] = field(default_factory=list)
    reasoning: str = ""
    ollama_model: str = ""
    processing_time_ms: int | None = None
