import unittest

import torch

from _loader import import_module

capabilities = import_module("py.api.capabilities")
video_generation = import_module("py.api.video_generation")


class CapabilityTests(unittest.TestCase):
    def test_text_request_is_valid(self):
        capabilities.validate_request("sora-2", "A slow camera pan", "4", "1280x720")

    def test_image_must_match_video_size(self):
        image = torch.zeros((1, 720, 1280, 3))
        with self.assertRaisesRegex(ValueError, "input_image is 1280x720"):
            capabilities.validate_request(
                "sora-2", "Animate this", "4", "720x1280", input_image=image
            )

    def test_image_request_builds_multipart_payload(self):
        image = torch.zeros((1, 720, 1280, 3))
        data, files = video_generation.build_create_request(
            "sora-2", "Animate this", "8", "1280x720", input_image=image
        )

        self.assertIsNone(data)
        names = [item[0] for item in files]
        self.assertEqual(
            names, ["model", "prompt", "seconds", "size", "input_reference"]
        )
        self.assertEqual(files[-1][1][2], "image/png")

    def test_text_request_is_also_multipart(self):
        data, files = video_generation.build_create_request(
            "sora-2", "A slow camera pan", "4", "1280x720"
        )
        self.assertIsNone(data)
        self.assertEqual([item[0] for item in files], ["model", "prompt", "seconds", "size"])


if __name__ == "__main__":
    unittest.main()
