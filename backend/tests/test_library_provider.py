import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from app.services import library_provider as provider


class GeminiConfigurationTests(unittest.TestCase):
    def test_free_tier_confirmation_required_before_key_is_read(self):
        with patch.object(provider, "settings", SimpleNamespace(
            LIBRARY_GEMINI_FREE_TIER_CONFIRMED=False,
            LIBRARY_GEMINI_KEY_FILE="/does-not-exist",
        )):
            with self.assertRaises(HTTPException) as error:
                provider.verified_key()
        self.assertIn("Free Tier", error.exception.detail)

    def test_key_file_must_be_private(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "gemini.key"
            key_file.write_text("test-key\n")
            key_file.chmod(0o600)
            settings = SimpleNamespace(
                LIBRARY_GEMINI_FREE_TIER_CONFIRMED=True,
                LIBRARY_GEMINI_KEY_FILE=str(key_file),
            )
            with patch.object(provider, "settings", settings):
                self.assertEqual(provider.verified_key(), "test-key")
                key_file.chmod(0o644)
                with self.assertRaises(HTTPException):
                    provider.verified_key()


class GeminiStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_uses_bounded_messages_and_reports_usage(self):
        captured = {}

        def reply(request):
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            stream = ("data: {\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"private thought\",\"thought\":true},{\"text\":\"Texto [1]\"}]}}]}\n\n"
                      "data: {\"candidates\":[{\"finishReason\":\"STOP\"}],\"usageMetadata\":{\"promptTokenCount\":20,\"candidatesTokenCount\":4,\"totalTokenCount\":24}}\n\n")
            return httpx.Response(200, text=stream)

        original_client = httpx.AsyncClient
        with patch.object(provider.httpx, "AsyncClient", side_effect=lambda **kwargs: original_client(
            transport=httpx.MockTransport(reply), **kwargs)):
            result = [item async for item in provider.generate("test-key", [
                {"role": "developer", "content": "Solo manuales"},
                {"role": "user", "content": "Pregunta y fragmento [1]"},
            ])]
        self.assertEqual(result, [("delta", "Texto [1]"),
                                  ("completed", {"promptTokenCount": 20,
                                                 "candidatesTokenCount": 4, "totalTokenCount": 24})])
        self.assertEqual(captured["url"], provider.ENDPOINT)
        self.assertEqual(captured["body"]["systemInstruction"]["parts"][0]["text"], "Solo manuales")
        self.assertEqual(captured["body"]["contents"][0]["role"], "user")
        self.assertEqual(captured["body"]["generationConfig"]["thinkingConfig"]["thinkingLevel"], "low")
        self.assertNotIn("tools", captured["body"])

    async def test_free_tier_limit_stops_without_retry(self):
        requests = []

        def reply(request):
            requests.append(request)
            return httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})

        original_client = httpx.AsyncClient
        with patch.object(provider.httpx, "AsyncClient", side_effect=lambda **kwargs: original_client(
            transport=httpx.MockTransport(reply), **kwargs)):
            with self.assertRaises(HTTPException) as error:
                _ = [item async for item in provider.generate("test-key", [
                    {"role": "user", "content": "Pregunta"},
                ])]
        self.assertEqual(len(requests), 1)
        self.assertIn("límite gratuito", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
