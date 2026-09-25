"""Ollama-Model-Benchmarking: analyze the same mails with several models and compare
accuracy/timing, per plan section 8.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mailorganizer.models.mail import MailData
from mailorganizer.services.analysis_service import AnalysisService
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.utils.exceptions import AnalysisError
from mailorganizer.utils.logger import get_logger

logger = get_logger("benchmark_service")


@dataclass
class BenchmarkMailResult:
    """A single model's analysis of a single mail during a benchmark run."""

    model: str
    mail_message_id: str
    category: str | None = None
    importance_score: int | None = None
    processing_time_ms: int | None = None
    error: str | None = None


@dataclass
class ModelBenchmarkSummary:
    """Aggregated results for one model across all benchmarked mails."""

    model: str
    mails_analyzed: int = 0
    errors: int = 0
    avg_processing_time_ms: float = 0.0


@dataclass
class BenchmarkReport:
    """Full result of a benchmark run: per-mail results and per-model summaries."""

    results: list[BenchmarkMailResult] = field(default_factory=list)
    summaries: list[ModelBenchmarkSummary] = field(default_factory=list)


class BenchmarkService:
    """Runs a fixed set of mails through several Ollama models and reports timing/results."""

    def __init__(self, ollama_service: OllamaService, temperature: float = 0.7, max_tokens: int = 500):
        self.ollama_service = ollama_service
        self.temperature = temperature
        self.max_tokens = max_tokens

    def run_benchmark(self, mails: list[MailData], models: list[str]) -> BenchmarkReport:
        """Analyze every mail with every model, returning per-mail results and per-model summaries."""
        results: list[BenchmarkMailResult] = []

        for model in models:
            analysis_service = AnalysisService(
                ollama_service=self.ollama_service,
                model=model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            for mail in mails:
                try:
                    result = analysis_service.analyze_mail(mail)
                    results.append(
                        BenchmarkMailResult(
                            model=model,
                            mail_message_id=mail.message_id,
                            category=result.category,
                            importance_score=result.importance_score,
                            processing_time_ms=result.processing_time_ms,
                        )
                    )
                except AnalysisError as exc:
                    logger.error("Benchmark: model %s failed on mail %s: %s", model, mail.message_id, exc)
                    results.append(
                        BenchmarkMailResult(model=model, mail_message_id=mail.message_id, error=str(exc))
                    )

        summaries = self._summarize(results, models)
        return BenchmarkReport(results=results, summaries=summaries)

    @staticmethod
    def _summarize(results: list[BenchmarkMailResult], models: list[str]) -> list[ModelBenchmarkSummary]:
        summaries: list[ModelBenchmarkSummary] = []
        for model in models:
            model_results = [r for r in results if r.model == model]
            successes = [r for r in model_results if r.error is None]
            errors = [r for r in model_results if r.error is not None]
            times = [r.processing_time_ms for r in successes if r.processing_time_ms is not None]
            avg_time = sum(times) / len(times) if times else 0.0
            summaries.append(
                ModelBenchmarkSummary(
                    model=model,
                    mails_analyzed=len(successes),
                    errors=len(errors),
                    avg_processing_time_ms=avg_time,
                )
            )
        return summaries
