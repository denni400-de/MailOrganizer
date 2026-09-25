from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.utils.exceptions import OllamaConnectionError


@patch("mailorganizer.services.ollama_service.requests.get")
def test_is_available_true(mock_get):
    mock_get.return_value = MagicMock(ok=True)
    service = OllamaService()
    assert service.is_available() is True


@patch("mailorganizer.services.ollama_service.requests.get")
def test_is_available_false_on_exception(mock_get):
    mock_get.side_effect = requests.RequestException("down")
    service = OllamaService()
    assert service.is_available() is False


@patch("mailorganizer.services.ollama_service.requests.get")
def test_list_models(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "mistral:latest"}, {"name": "llama3:latest"}]}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    service = OllamaService()
    models = service.list_models()

    assert models == ["mistral:latest", "llama3:latest"]


@patch("mailorganizer.services.ollama_service.requests.get")
def test_list_models_connection_error(mock_get):
    mock_get.side_effect = requests.RequestException("boom")
    service = OllamaService()
    with pytest.raises(OllamaConnectionError):
        service.list_models()


@patch("mailorganizer.services.ollama_service.requests.post")
def test_generate_non_streaming(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "hello", "total_duration": 2_000_000}
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    service = OllamaService()
    result = service.generate(model="mistral:latest", prompt="hi")

    assert result.text == "hello"
    assert result.model == "mistral:latest"
    assert result.total_duration_ms == 2


@patch("mailorganizer.services.ollama_service.requests.post")
def test_generate_connection_error(mock_post):
    mock_post.side_effect = requests.RequestException("boom")
    service = OllamaService()
    with pytest.raises(OllamaConnectionError):
        service.generate(model="mistral:latest", prompt="hi")
