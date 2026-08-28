import importlib
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import SecretStr


main = importlib.import_module("app.main")
security = importlib.import_module("app.security")

TEST_API_KEY = "unit-test-api-key"
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


class FakeSession:
    async def execute(self, _):
        return FakeResult()


class FakeResult:
    def scalar(self):
        return 1


async def fake_session():
    yield FakeSession()


def successful_state():
    return {
        "answer": "Mocked answer.",
        "citations": [],
        "route": "retrieve_docs",
        "confidence": 1.0,
    }


class SecurityBaselineTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides[main.get_session] = fake_session
        self.original_api_key = main.settings.setu_api_key
        self.original_limiter = security.query_rate_limiter
        main.settings.setu_api_key = SecretStr(TEST_API_KEY)
        security.query_rate_limiter = security.InMemoryRateLimiter(1_000, 60)

    def tearDown(self):
        main.app.dependency_overrides.clear()
        main.settings.setu_api_key = self.original_api_key
        security.query_rate_limiter = self.original_limiter

    def test_health_is_public_but_query_requires_key(self):
        agent = AsyncMock(return_value=successful_state())
        with patch.object(main, "run_agent", agent), TestClient(main.app) as client:
            health = client.get("/health")
            missing = client.post("/query", json={"query": "test"})

        self.assertEqual(health.status_code, 200)
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(
            missing.json()["error"]["code"], "authentication_required"
        )
        self.assertEqual(
            missing.json()["error"]["request_id"],
            missing.headers["x-request-id"],
        )
        agent.assert_not_awaited()

    def test_invalid_key_is_rejected_without_secret_exposure(self):
        invalid = "invalid-key-must-not-appear"
        with self.assertLogs("app", level="WARNING") as captured:
            with TestClient(main.app) as client:
                response = client.post(
                    "/query",
                    json={"query": "test"},
                    headers={"X-API-Key": invalid},
                )

        self.assertEqual(response.status_code, 401)
        self.assertNotIn(invalid, response.text)
        self.assertNotIn(invalid, "\n".join(captured.output))

    def test_valid_key_allows_mocked_query(self):
        agent = AsyncMock(return_value=successful_state())
        with patch.object(main, "run_agent", agent), TestClient(main.app) as client:
            response = client.post(
                "/query", json={"query": "test"}, headers=AUTH_HEADERS
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Mocked answer.")
        agent.assert_awaited_once()

    def test_missing_server_key_fails_closed(self):
        with patch.object(main.settings, "setu_api_key", None):
            with TestClient(main.app) as client:
                response = client.post(
                    "/query", json={"query": "test"}, headers=AUTH_HEADERS
                )
                readiness = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"], "configuration_unavailable"
        )
        self.assertEqual(readiness.status_code, 503)
        self.assertIn("api_auth_not_configured", readiness.json()["issues"])

    def test_rate_limit_returns_safe_429(self):
        security.query_rate_limiter = security.InMemoryRateLimiter(1, 60)
        agent = AsyncMock(return_value=successful_state())
        with patch.object(main, "run_agent", agent), TestClient(main.app) as client:
            first = client.post(
                "/query", json={"query": "first"}, headers=AUTH_HEADERS
            )
            second = client.post(
                "/query", json={"query": "second"}, headers=AUTH_HEADERS
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"]["code"], "rate_limit_exceeded")
        self.assertEqual(
            second.json()["error"]["request_id"],
            second.headers["x-request-id"],
        )

    def test_cors_allows_configured_origin(self):
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        }
        with TestClient(main.app) as client:
            response = client.options("/query", headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:3000",
        )
        self.assertNotIn("access-control-allow-credentials", response.headers)

    def test_cors_denies_unconfigured_origin(self):
        headers = {
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key",
        }
        with TestClient(main.app) as client:
            response = client.options("/query", headers=headers)

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_security_headers_are_present(self):
        with TestClient(main.app) as client:
            response = client.get("/health")

        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_oversized_body_is_rejected_before_processing(self):
        oversized = "x" * (main.settings.max_request_body_bytes + 1)
        with TestClient(main.app) as client:
            response = client.post(
                "/query",
                content=oversized,
                headers={**AUTH_HEADERS, "Content-Type": "application/json"},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "request_too_large")

    def test_query_length_limit_returns_safe_422(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/query",
                json={"query": "x" * 2001},
                headers=AUTH_HEADERS,
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")
        self.assertNotIn("x" * 100, response.text)


if __name__ == "__main__":
    unittest.main()
