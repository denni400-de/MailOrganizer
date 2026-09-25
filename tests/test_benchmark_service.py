from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from mailorganizer.models.mail import MailData
from mailorganizer.services.benchmark_service import BenchmarkService
from mailorganizer.services.ollama_service import OllamaResponse


def make_mail(message_id) -> MailData:
    return MailData(
        message_id=message_id,
        sender="s@x.com",
        recipients=["a@b.com"],
        subject="Subject",
        received_at=datetime.now(),
        body="Please review this report.",
    )


def make_ollama_response(category="work", importance=3):
    return OllamaResponse(
        text=(
            f'{{"category": "{category}", "importance_score": {importance}, "sentiment": "neutral", '
            '"summary": "s", "recommended_action": "archive", "keywords": []}'
        ),
        model="mistral:latest",
        total_duration_ms=5,
    )


def test_run_benchmark_across_models():
    ollama = MagicMock()
    ollama.generate.return_value = make_ollama_response()

    mails = [make_mail("<1@x>"), make_mail("<2@x>")]
    report = BenchmarkService(ollama).run_benchmark(mails, ["mistral:latest", "llama3:latest"])

    assert len(report.results) == 4
    assert len(report.summaries) == 2
    for summary in report.summaries:
        assert summary.mails_analyzed == 2
        assert summary.errors == 0


def test_run_benchmark_records_errors():
    ollama = MagicMock()
    ollama.generate.side_effect = RuntimeError("connection lost")

    mails = [make_mail("<1@x>")]
    report = BenchmarkService(ollama).run_benchmark(mails, ["mistral:latest"])

    assert len(report.results) == 1
    assert report.results[0].error is not None
    assert report.summaries[0].mails_analyzed == 0
    assert report.summaries[0].errors == 1


def test_summarize_computes_average_time():
    ollama = MagicMock()
    ollama.generate.side_effect = [make_ollama_response(), make_ollama_response()]

    mails = [make_mail("<1@x>"), make_mail("<2@x>")]
    report = BenchmarkService(ollama).run_benchmark(mails, ["mistral:latest"])

    assert report.summaries[0].avg_processing_time_ms >= 0
