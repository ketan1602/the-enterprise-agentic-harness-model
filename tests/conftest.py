from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.fake_llm import FakeLLM


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    """No test reaches the real API: the client is replaced for every test."""
    llm = FakeLLM()
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.test/v1")
    client = MagicMock()
    client.chat.completions.create = llm.create
    with patch("openai.AsyncOpenAI", return_value=client):
        yield llm
