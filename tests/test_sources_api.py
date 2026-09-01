import importlib
import unittest
from uuid import UUID
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import SecretStr


main = importlib.import_module("app.main")
security = importlib.import_module("app.security")
TEST_API_KEY = "source-test-api-key"
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


class SourceApiTests(unittest.TestCase):
    def setUp(self):
        self.original_key = main.settings.setu_api_key
        main.settings.setu_api_key = SecretStr(TEST_API_KEY)

    def tearDown(self):
        main.settings.setu_api_key = self.original_key
        main.app.dependency_overrides.clear()

    def test_sources_require_authentication_without_database_access(self):
        with patch.object(main, "list_sources", AsyncMock()) as service:
            with TestClient(main.app) as client:
                response = client.get("/sources")
        self.assertEqual(response.status_code, 401)
        service.assert_not_awaited()

    def test_sources_pass_bounded_validated_filters(self):
        payload = {
            "items": [], "page": 2, "page_size": 5, "total": 0,
            "total_pages": 0,
        }
        with patch.object(main, "list_sources", AsyncMock(return_value=payload)) as service:
            with TestClient(main.app) as client:
                response = client.get(
                    "/sources?page=2&page_size=5&search=%25_%27&language=en&has_eligibility=true",
                    headers=AUTH_HEADERS,
                )
        self.assertEqual(response.status_code, 200)
        service.assert_awaited_once()
        arguments = service.await_args.kwargs
        self.assertEqual(arguments["search"], "%_'")
        self.assertEqual(arguments["language"], "en")
        self.assertTrue(arguments["has_eligibility"])

    def test_sources_reject_unbounded_or_invalid_parameters(self):
        with TestClient(main.app) as client:
            too_many = client.get("/sources?page_size=26", headers=AUTH_HEADERS)
            bad_language = client.get("/sources?language=fr", headers=AUTH_HEADERS)
            long_search = client.get(
                "/sources?search=" + ("x" * 101), headers=AUTH_HEADERS
            )
        for response in (too_many, bad_language, long_search):
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "invalid_request")

    def test_source_detail_uses_validated_uuid_and_safe_service_contract(self):
        source_id = UUID("11111111-1111-1111-1111-111111111111")
        payload = {
            "id": str(source_id), "title": "Safe title", "source": "PIB",
            "language": "en", "metadata": {"posted_on": "2025-01-01"},
            "chunk_count": 4, "eligibility_count": 1,
            "has_eligibility": True,
            "eligibility": [{"scheme_name": "Example", "criteria": {"min_age": 18}}],
        }
        with patch.object(main, "get_source", AsyncMock(return_value=payload)) as service:
            with TestClient(main.app) as client:
                response = client.get(f"/sources/{source_id}", headers=AUTH_HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("raw_text", response.text)
        self.assertNotIn("content", response.text)
        service.assert_awaited_once()

    def test_invalid_identifier_is_sanitized_and_never_reaches_service(self):
        with patch.object(main, "get_source", AsyncMock()) as service:
            with TestClient(main.app) as client:
                response = client.get(
                    "/sources/not-a-uuid%27%20OR%201%3D1", headers=AUTH_HEADERS
                )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("traceback", response.text.lower())
        service.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
