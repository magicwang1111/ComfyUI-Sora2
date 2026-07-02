import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _loader import ensure_package_loaded, import_module

ensure_package_loaded()
from comfy_api.latest import InputImpl

nodes = import_module("py.nodes")


class FakeClient:
    def __init__(self):
        self.create_calls = []
        self.closed = False

    async def create_video(self, data, files):
        self.create_calls.append((data, files))
        return {"id": "video_123", "status": "queued", "progress": 0}

    async def poll_video(self, video):
        return {
            **video,
            "status": "completed",
            "progress": 100,
            "model": "custom-deployment",
        }

    async def download_video(self, video_id):
        return b"fake mp4 bytes"

    async def close(self):
        self.closed = True


class NodeTests(unittest.TestCase):
    def test_nodes_are_registered(self):
        package = ensure_package_loaded()
        self.assertIn("ComfyUI-Sora2 Text to Video", package.NODE_CLASS_MAPPINGS)
        self.assertIn("ComfyUI-Sora2 Image to Video", package.NODE_CLASS_MAPPINGS)

    def test_text_node_returns_native_video(self):
        client = FakeClient()
        with patch.object(nodes, "_create_runtime_client", return_value=client):
            video, response_json = asyncio.run(
                nodes.Sora2TextToVideoNode().generate(
                    "A paper boat on a stream",
                    model_override="custom-deployment",
                    size="1280x720",
                )
            )

        self.assertIsInstance(video, InputImpl.VideoFromFile)
        self.assertEqual(json.loads(response_json)["status"], "completed")
        outbound_files = client.create_calls[0][1]
        self.assertIn(("model", (None, "custom-deployment")), outbound_files)
        self.assertTrue(client.closed)

    def test_azure_endpoint_is_normalized(self):
        self.assertEqual(
            nodes._normalize_azure_base_url("https://example.openai.azure.com"),
            "https://example.openai.azure.com/openai/v1",
        )

    def test_runtime_config_resolves_azure_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.local.json"
            path.write_text(
                json.dumps(
                    {
                        "api_key": "test-key",
                        "api_provider": "azure",
                        "base_url": "https://example.openai.azure.com",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(nodes, "CONFIG_JSON_PATH", path):
                kwargs = nodes._resolve_runtime_client_kwargs()

        self.assertEqual(kwargs["api_key"], "test-key")
        self.assertEqual(
            kwargs["base_url"], "https://example.openai.azure.com/openai/v1"
        )
        self.assertEqual(kwargs["api_provider"], "azure")


if __name__ == "__main__":
    unittest.main()
