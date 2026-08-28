import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.config import Settings


class SettingsTests(unittest.TestCase):
    def test_pytorch_is_default(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.local_inference_backend, "pytorch")

    def test_openvino_is_valid(self):
        settings = Settings(_env_file=None, local_inference_backend="openvino")
        self.assertEqual(settings.local_inference_backend, "openvino")

    def test_invalid_backend_fails_clearly(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, local_inference_backend="cuda")


if __name__ == "__main__":
    unittest.main()
