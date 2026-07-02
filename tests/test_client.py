import asyncio
import unittest

import httpx

from _loader import import_module

client_module = import_module("py.api.client")


class ClientTests(unittest.TestCase):
    def test_azure_uses_api_key_header(self):
        headers = client_module._headers("secret", "azure")
        self.assertEqual(headers, {"api-key": "secret"})

    def test_openai_uses_bearer_header(self):
        headers = client_module._headers("secret", "openai")
        self.assertEqual(headers, {"Authorization": "Bearer secret"})

    def test_create_accepts_201_and_uses_videos_path(self):
        captured = {}

        async def run():
            def handler(request):
                captured["method"] = request.method
                captured["path"] = request.url.path
                captured["content_type"] = request.headers["content-type"]
                return httpx.Response(
                    201,
                    json={"id": "video_123", "status": "queued"},
                    request=request,
                )

            client = client_module.AsyncClient(
                "secret", "azure", base_url="https://example.test/openai/v1"
            )
            await client._client.aclose()
            client._client = httpx.AsyncClient(
                base_url=client.base_url,
                transport=httpx.MockTransport(handler),
            )
            try:
                result = await client.create_video(
                    None, [("model", (None, "sora-2")), ("prompt", (None, "test"))]
                )
            finally:
                await client.close()
            return result

        result = asyncio.run(run())
        self.assertEqual(result["id"], "video_123")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/openai/v1/videos")
        self.assertIn("multipart/form-data", captured["content_type"])

    def test_poll_returns_completed_initial_job_without_sleep(self):
        async def run():
            client = client_module.AsyncClient(
                "secret", "azure", base_url="https://example.test/openai/v1"
            )
            try:
                return await client.poll_video(
                    {"id": "video_123", "status": "completed", "progress": 100}
                )
            finally:
                await client.close()

        result = asyncio.run(run())
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
