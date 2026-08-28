import importlib
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from app.errors import (
    DatabaseUnavailableError,
    LLMProviderError,
    RetrievalUnavailableError,
)


main = importlib.import_module("app.main")


class FakeResult:
    def __init__(self, value=1):
        self.value = value

    def scalar(self):
        return self.value


class HealthySession:
    async def execute(self, _):
        return FakeResult()


class UnavailableSession:
    async def execute(self, _):
        raise OperationalError("SELECT 1", {}, Exception("database secret"))


async def healthy_session():
    yield HealthySession()


async def unavailable_session():
    yield UnavailableSession()


class OperationalEndpointTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides.clear()

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_health_exposes_backend_and_request_id(self):
        with TestClient(main.app) as client:
            first = client.get("/health")
            second = client.get("/health")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["status"], "ok")
        self.assertEqual(
            first.json()["inference_backend"],
            main.settings.local_inference_backend,
        )
        self.assertRegex(first.headers["x-request-id"], r"^[0-9a-f]{32}$")
        self.assertNotEqual(
            first.headers["x-request-id"], second.headers["x-request-id"]
        )

    def test_database_health_success(self):
        main.app.dependency_overrides[main.get_session] = healthy_session
        with TestClient(main.app) as client:
            response = client.get("/health/db")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"db": "ok"})

    def test_database_health_failure_is_safe(self):
        main.app.dependency_overrides[main.get_session] = unavailable_session
        with TestClient(main.app) as client:
            response = client.get("/health/db")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "database_unavailable")
        self.assertNotIn("database secret", response.text)
        self.assertNotIn("SELECT 1", response.text)

    def test_readiness_success_reports_safe_operational_metadata(self):
        main.app.dependency_overrides[main.get_session] = healthy_session
        with (
            patch.object(main.settings, "groq_api_key", "test-key"),
            patch.object(main.settings, "gemini_api_key", None),
            patch.object(main.settings, "local_inference_backend", "pytorch"),
            TestClient(main.app) as client,
        ):
            response = client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ready",
                "database": "ok",
                "inference_backend": "pytorch",
                "inference_ready": True,
                "llm_provider": "groq",
            },
        )

    def test_readiness_reports_missing_llm_without_loading_models(self):
        main.app.dependency_overrides[main.get_session] = healthy_session
        with (
            patch.object(main.settings, "groq_api_key", None),
            patch.object(main.settings, "gemini_api_key", None),
            patch.object(main.settings, "local_inference_backend", "pytorch"),
            TestClient(main.app) as client,
        ):
            response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")
        self.assertIn("llm_not_configured", response.json()["issues"])

    def test_readiness_reports_missing_openvino_artifacts(self):
        main.app.dependency_overrides[main.get_session] = healthy_session
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(main.settings, "groq_api_key", "test-key"),
            patch.object(main.settings, "local_inference_backend", "openvino"),
            patch.object(main.settings, "openvino_model_dir", directory),
            TestClient(main.app) as client,
        ):
            response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["inference_backend"], "openvino")
        self.assertFalse(response.json()["inference_ready"])
        self.assertIn("openvino_artifacts_missing", response.json()["issues"])

    def test_readiness_reports_database_failure(self):
        main.app.dependency_overrides[main.get_session] = unavailable_session
        with (
            patch.object(main.settings, "groq_api_key", "test-key"),
            TestClient(main.app) as client,
        ):
            response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["database"], "error")
        self.assertIn("database_unavailable", response.json()["issues"])

    def test_invalid_request_uses_stable_safe_error(self):
        main.app.dependency_overrides[main.get_session] = healthy_session
        with TestClient(main.app) as client:
            response = client.post("/query", json={"query": ""})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")
        self.assertEqual(
            response.json()["error"]["request_id"],
            response.headers["x-request-id"],
        )

    def test_query_failures_are_distinguishable_and_safe(self):
        main.app.dependency_overrides[main.get_session] = healthy_session
        cases = (
            (RetrievalUnavailableError(), 503, "retrieval_unavailable"),
            (LLMProviderError(), 502, "llm_provider_unavailable"),
        )
        with TestClient(main.app) as client:
            for error, status, code in cases:
                with patch.object(
                    main, "run_agent", AsyncMock(side_effect=error)
                ):
                    response = client.post("/query", json={"query": "test"})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["error"]["code"], code)
                self.assertNotIn("traceback", response.text.lower())

    def test_unexpected_error_does_not_expose_secret_or_traceback(self):
        main.app.dependency_overrides[main.get_session] = healthy_session
        secret = "GROQ_API_KEY=do-not-expose"
        with (
            self.assertLogs("app.main", level="ERROR") as captured,
            patch.object(main, "run_agent", AsyncMock(side_effect=RuntimeError(secret))),
            TestClient(main.app, raise_server_exceptions=False) as client,
        ):
            response = client.post("/query", json={"query": "test"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "internal_error")
        self.assertNotIn(secret, response.text)
        self.assertNotIn("traceback", response.text.lower())
        self.assertNotIn(secret, "\n".join(captured.output))

    def test_startup_and_request_completion_are_logged(self):
        with self.assertLogs("app", level="INFO") as captured:
            with TestClient(main.app) as client:
                client.get("/health")
        logs = "\n".join(captured.output)
        self.assertIn("application_startup backend=", logs)
        self.assertIn("request_complete request_id=", logs)


class FailureClassificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_retrieval_classifies_model_and_database_failures(self):
        pipeline = importlib.import_module("app.retrieval.pipeline")
        with patch.object(
            pipeline, "embed_chunks", side_effect=RuntimeError("model secret")
        ):
            with self.assertRaises(RetrievalUnavailableError):
                await pipeline.retrieve(HealthySession(), "test")

        database_error = OperationalError("SELECT", {}, Exception("db secret"))
        with (
            patch.object(pipeline, "embed_chunks", return_value=[[0.0]]),
            patch.object(
                pipeline, "dense_search", AsyncMock(side_effect=database_error)
            ),
        ):
            with self.assertRaises(DatabaseUnavailableError):
                await pipeline.retrieve(HealthySession(), "test")

    async def test_llm_initialization_failure_is_classified_without_secret_log(self):
        llm = importlib.import_module("app.agent.llm")

        class Response(BaseModel):
            value: str

        secret = "GROQ_API_KEY=provider-secret"
        with (
            self.assertLogs("app.agent.llm", level="ERROR") as captured,
            patch.object(llm, "_get_client", side_effect=RuntimeError(secret)),
        ):
            with self.assertRaises(LLMProviderError):
                llm.generate_structured(
                    system_prompt="system",
                    user_prompt="user",
                    response_model=Response,
                )
        self.assertNotIn(secret, "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
