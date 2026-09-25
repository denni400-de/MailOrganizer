"""Client for talking to a local Ollama server."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from mailorganizer.utils.exceptions import OllamaConnectionError, OllamaResponseError
from mailorganizer.utils.logger import get_logger

logger = get_logger("ollama_service")

DEFAULT_TIMEOUT = 60


@dataclass
class OllamaResponse:
    """Raw text response from an Ollama /api/generate call, plus timing."""

    text: str
    model: str
    total_duration_ms: int | None = None


class OllamaService:
    """Wraps the Ollama HTTP API for model listing and prompt generation."""

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        """Return True if the Ollama server responds to a basic ping."""
        try:
            resp = requests.get(f"{self.base_url}/api/version", timeout=5)
            return resp.ok
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        """Return the names of models currently available on the Ollama server."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except requests.RequestException as exc:
            logger.error("Failed to list Ollama models: %s", exc)
            raise OllamaConnectionError(f"Failed to list Ollama models: {exc}") from exc

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        stream: bool = False,
    ) -> OllamaResponse:
        """Generate a completion from the given model. Non-streaming by default."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system

        try:
            if stream:
                return self._generate_streaming(payload, model)
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return OllamaResponse(
                text=data.get("response", ""),
                model=model,
                total_duration_ms=self._ns_to_ms(data.get("total_duration")),
            )
        except requests.RequestException as exc:
            logger.error("Ollama generate failed: %s", exc)
            raise OllamaConnectionError(f"Ollama generate failed: {exc}") from exc
        except ValueError as exc:
            raise OllamaResponseError(f"Invalid JSON from Ollama: {exc}") from exc

    def _generate_streaming(self, payload: dict, model: str) -> OllamaResponse:
        import json

        chunks: list[str] = []
        total_duration = None
        try:
            with requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout, stream=True) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    obj = json.loads(line)
                    chunks.append(obj.get("response", ""))
                    if obj.get("done"):
                        total_duration = obj.get("total_duration")
        except requests.RequestException as exc:
            raise OllamaConnectionError(f"Ollama streaming generate failed: {exc}") from exc

        return OllamaResponse(text="".join(chunks), model=model, total_duration_ms=self._ns_to_ms(total_duration))

    @staticmethod
    def _ns_to_ms(nanoseconds: int | None) -> int | None:
        return int(nanoseconds / 1_000_000) if nanoseconds is not None else None
