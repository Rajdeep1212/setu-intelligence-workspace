import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.config import OPENVINO_MODELS, OPENVINO_REQUIRED_FILES, Settings


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

    def test_database_url_is_validated_without_exposing_input(self):
        secret = "do-not-expose-this-password"
        with self.assertRaises(ValidationError) as raised:
            Settings(_env_file=None, database_url=f"not-a-url-{secret}")
        self.assertNotIn(secret, str(raised.exception))

    def test_llm_provider_precedence_and_missing_configuration(self):
        missing = Settings(_env_file=None)
        self.assertIsNone(missing.llm_provider)
        self.assertIn("llm_not_configured", missing.operational_issues())

        configured = Settings(
            _env_file=None,
            groq_api_key="test-groq",
            gemini_api_key="test-gemini",
        )
        self.assertEqual(configured.llm_provider, "groq")

    def test_openvino_artifact_readiness_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                _env_file=None,
                groq_api_key="test",
                setu_api_key="test-api-key",
                local_inference_backend="openvino",
                openvino_model_dir=directory,
            )
            self.assertFalse(settings.openvino_artifacts_ready())
            self.assertIn("openvino_artifacts_missing", settings.operational_issues())

            root = Path(directory)
            for model in OPENVINO_MODELS:
                model_dir = root / model
                model_dir.mkdir()
                for filename in OPENVINO_REQUIRED_FILES:
                    (model_dir / filename).touch()
            self.assertTrue(settings.openvino_artifacts_ready())
            self.assertEqual(settings.operational_issues(), [])

    def test_api_key_is_secret_and_required_for_readiness(self):
        missing = Settings(_env_file=None, groq_api_key="test")
        self.assertIn("api_auth_not_configured", missing.operational_issues())

        value = "unit-test-placeholder"
        configured = Settings(
            _env_file=None, groq_api_key="test", setu_api_key=value
        )
        self.assertNotIn(value, repr(configured))
        self.assertEqual(configured.setu_api_key.get_secret_value(), value)

    def test_rate_limit_and_body_size_are_validated(self):
        for field in (
            {"query_rate_limit": 0},
            {"query_rate_window_seconds": 0},
            {"max_request_body_bytes": 100},
        ):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None, **field)

    def test_external_timeout_retry_and_database_pool_limits_are_validated(self):
        invalid_fields = (
            {"groq_request_timeout_seconds": 0},
            {"groq_connect_timeout_seconds": 0},
            {"groq_max_retries": -1},
            {"database_pool_size": 0},
            {"database_max_overflow": -1},
            {"database_pool_timeout_seconds": 0},
            {"database_pool_recycle_seconds": 1},
        )
        for field in invalid_fields:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Settings(_env_file=None, **field)

    def test_cors_origins_are_explicit_and_wildcards_are_rejected(self):
        configured = Settings(
            _env_file=None,
            cors_allowed_origins="https://app.example,http://localhost:3000/",
        )
        self.assertEqual(
            configured.cors_origins,
            ["https://app.example", "http://localhost:3000"],
        )
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, cors_allowed_origins="*")


if __name__ == "__main__":
    unittest.main()
