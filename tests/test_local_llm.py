import io
import json
import unittest
from unittest.mock import patch

from flowguard.local_llm import (
    LocalLLMError, LocalModelConfig, fallback_suggestion,
    generate_suggestion, list_models,
)


class FakeResponse:
    def __init__(self, payload):
        self.buffer = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self): return self.buffer
    def __exit__(self, *_args): return False


class LocalLLMTests(unittest.TestCase):
    def test_rejects_remote_endpoint(self):
        with self.assertRaises(LocalLLMError):
            LocalModelConfig("Ollama", "model", "https://example.com").validated()

    @patch("urllib.request.urlopen", side_effect=OSError("offline"))
    def test_connection_failure_is_wrapped(self, _mock):
        with self.assertRaises(LocalLLMError):
            generate_suggestion("summary", LocalModelConfig(), timeout=0.01)

    @patch("urllib.request.urlopen")
    def test_retries_first_generation_disconnect(self, request):
        request.side_effect = [OSError("first load failed"), FakeResponse({"response": "재시도 성공"})]
        self.assertEqual("재시도 성공", generate_suggestion("summary", LocalModelConfig()))
        self.assertEqual(2, request.call_count)

    @patch("urllib.request.urlopen")
    def test_lists_ollama_models(self, request):
        request.return_value = FakeResponse({"models": [{"name": "qwen:4b"}, {"name": "qwen:9b"}]})
        self.assertEqual(["qwen:4b", "qwen:9b"], list_models(LocalModelConfig()))

    @patch("urllib.request.urlopen")
    def test_openai_compatible_response(self, request):
        request.return_value = FakeResponse({"choices": [{"message": {"content": "안전한 제안"}}]})
        config = LocalModelConfig("OpenAI 호환", "qwen.gguf", "http://localhost:8080/v1")
        self.assertEqual("안전한 제안", generate_suggestion("PDF 3개", config))

    def test_fallback_is_safe_and_clear(self):
        text = fallback_suggestion("PDF 3개")
        self.assertIn("드라이런", text)
        self.assertIn("PDF 3개", text)
