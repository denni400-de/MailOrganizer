"""Builds prompts, calls Ollama and parses the structured analysis result."""

from __future__ import annotations

import json
import re
import time

from mailorganizer.config import constants
from mailorganizer.models.analysis import AnalysisResult
from mailorganizer.models.mail import MailData
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.utils.email_utils import strip_html, truncate_body
from mailorganizer.utils.exceptions import AnalysisError
from mailorganizer.utils.logger import get_logger

logger = get_logger("analysis_service")

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


class AnalysisService:
    """Runs LLM-based analysis of mails via an OllamaService."""

    def __init__(self, ollama_service: OllamaService, model: str, temperature: float = 0.7, max_tokens: int = 500):
        self.ollama_service = ollama_service
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def build_prompt(
        self,
        mail: MailData,
        email_number: int = 1,
        user_language: str = "Deutsch",
        user_preferences: str = "",
    ) -> str:
        """Build the user prompt for a single mail, per the template in IMPLEMENTATION_PLAN.md."""
        body_text = mail.body or strip_html(mail.html_body)
        return constants.ANALYSIS_USER_PROMPT_TEMPLATE.format(
            sender=mail.sender,
            subject=mail.subject,
            date=mail.received_at.isoformat(),
            body_excerpt=truncate_body(body_text),
            email_number=email_number,
            user_language=user_language,
            user_preferences=user_preferences or "keine",
        )

    def analyze_mail(
        self,
        mail: MailData,
        email_number: int = 1,
        user_language: str = "Deutsch",
        user_preferences: str = "",
    ) -> AnalysisResult:
        """Analyze a single mail and return a structured AnalysisResult."""
        prompt = self.build_prompt(mail, email_number, user_language, user_preferences)
        start = time.monotonic()
        try:
            response = self.ollama_service.generate(
                model=self.model,
                prompt=prompt,
                system=constants.ANALYSIS_SYSTEM_PROMPT,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:
            raise AnalysisError(f"Ollama analysis failed for mail {mail.message_id}: {exc}") from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)
        result = self.parse_response(response.text)
        result.ollama_model = self.model
        result.processing_time_ms = elapsed_ms
        return result

    @staticmethod
    def parse_response(raw_text: str) -> AnalysisResult:
        """Parse the JSON analysis object out of the LLM's raw text response."""
        match = _JSON_BLOCK_RE.search(raw_text or "")
        if not match:
            raise AnalysisError(f"No JSON object found in Ollama response: {raw_text!r}")

        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Could not parse JSON from Ollama response: {exc}") from exc

        category = data.get("category", "other")
        if category not in constants.CATEGORIES:
            category = "other"

        action = data.get("recommended_action", "read_later")
        if action not in constants.RECOMMENDED_ACTIONS:
            action = "read_later"

        sentiment = data.get("sentiment", "neutral")
        if sentiment not in constants.SENTIMENTS:
            sentiment = "neutral"

        try:
            importance = int(data.get("importance_score", 1))
        except (TypeError, ValueError):
            importance = 1
        importance = max(constants.IMPORTANCE_MIN, min(constants.IMPORTANCE_MAX, importance))

        keywords = data.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []

        return AnalysisResult(
            category=category,
            importance_score=importance,
            sentiment=sentiment,
            summary=str(data.get("summary", "")),
            recommended_action=action,
            keywords=[str(k) for k in keywords],
            reasoning=str(data.get("reasoning", "")),
        )
