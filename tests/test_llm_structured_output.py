import asyncio
import importlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from openai import BadRequestError, OpenAI
from pydantic import SecretStr, ValidationError

from app.agent.models import GeneratedAnswer, RouteDecision
from app.errors import LLMProviderError


llm = importlib.import_module("app.agent.llm")
graph = importlib.import_module("app.agent.graph")
main = importlib.import_module("app.main")
security = importlib.import_module("app.security")


def _completion(content: str) -> dict:
    return {
        "id": "offline-completion",
        "object": "chat.completion",
        "created": 1,
        "model": "openai/gpt-oss-20b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _recording_client(payloads: list[dict], content: str) -> OpenAI:
    def handle(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=_completion(content), request=request)

    return OpenAI(
        api_key="offline-test-key",
        base_url="https://offline.invalid/openai/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )


def _assert_objects_are_closed(test: unittest.TestCase, schema: object) -> None:
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            test.assertIs(schema.get("additionalProperties"), False)
            test.assertEqual(
                set(schema.get("required", [])), set(schema.get("properties", {}))
            )
        for value in schema.values():
            _assert_objects_are_closed(test, value)
    elif isinstance(schema, list):
        for value in schema:
            _assert_objects_are_closed(test, value)


class NativeJSONSchemaTests(unittest.TestCase):
    def _generate(self, response_model, payload, *, stage="route_decision"):
        requests: list[dict] = []
        client = _recording_client(requests, json.dumps(payload, ensure_ascii=False))
        with patch.object(llm, "_get_client", return_value=(client, "groq")):
            parsed = llm.generate_structured(
                stage=stage,
                system_prompt="offline system prompt",
                user_prompt="offline user prompt",
                response_model=response_model,
            )
        self.assertEqual(len(requests), 1)
        return parsed, requests[0]

    def test_route_request_uses_native_strict_json_schema_without_tools(self):
        parsed, request = self._generate(
            RouteDecision,
            {"route": "retrieve_docs", "scheme_name_hint": None},
        )

        self.assertEqual(parsed.route, "retrieve_docs")
        self.assertIsNone(parsed.scheme_name_hint)
        self.assertNotIn("tools", request)
        self.assertNotIn("tool_choice", request)
        response_format = request["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertIs(response_format["json_schema"]["strict"], True)

        schema = response_format["json_schema"]["schema"]
        self.assertEqual(set(schema["required"]), {"route", "scheme_name_hint"})
        self.assertIs(schema["additionalProperties"], False)
        nullable = schema["properties"]["scheme_name_hint"]["anyOf"]
        self.assertEqual({entry["type"] for entry in nullable}, {"string", "null"})
        _assert_objects_are_closed(self, schema)

    def test_answer_schema_preserves_constraints(self):
        _, request = self._generate(
            GeneratedAnswer,
            {
                "answer": "Grounded answer",
                "confidence": 0.75,
                "citation_ids": ["chunk-1"],
                "abstained": False,
            },
            stage="answer_generation",
        )

        self.assertNotIn("tools", request)
        self.assertNotIn("tool_choice", request)
        response_format = request["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertIs(response_format["json_schema"]["strict"], True)
        schema = response_format["json_schema"]["schema"]
        self.assertEqual(
            set(schema["required"]),
            {"answer", "confidence", "citation_ids", "abstained"},
        )
        self.assertEqual(schema["properties"]["confidence"]["minimum"], 0)
        self.assertEqual(schema["properties"]["confidence"]["maximum"], 1)
        self.assertEqual(schema["properties"]["citation_ids"]["maxItems"], 5)
        _assert_objects_are_closed(self, schema)

    def test_unicode_answers_parse_for_all_supported_languages(self):
        values = ("Grounded answer", "सत्यापित उत्तर", "যাচাইকৃত উত্তর")
        for value in values:
            with self.subTest(value=value):
                parsed, _ = self._generate(
                    GeneratedAnswer,
                    {
                        "answer": value,
                        "confidence": 1.0,
                        "citation_ids": ["প্রমাণ"],
                        "abstained": False,
                    },
                    stage="answer_generation",
                )
                self.assertEqual(parsed.answer, value)
                self.assertEqual(parsed.citation_ids, ["প্রমাণ"])

    def test_models_reject_extra_properties_and_keep_none_default(self):
        self.assertIsNone(RouteDecision(route="retrieve_docs").scheme_name_hint)
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                {
                    "route": "retrieve_docs",
                    "scheme_name_hint": None,
                    "unexpected": True,
                }
            )
        with self.assertRaises(ValidationError):
            GeneratedAnswer.model_validate(
                {
                    "answer": "answer",
                    "confidence": 0.5,
                    "citation_ids": [],
                    "abstained": False,
                    "unexpected": True,
                }
            )


class StageAndDiagnosticsTests(unittest.TestCase):
    def test_graph_passes_both_stage_labels(self):
        route_result = RouteDecision(
            route="retrieve_docs", scheme_name_hint=None
        )
        with patch.object(graph, "generate_structured", return_value=route_result) as call:
            asyncio.run(graph.route_node({"query": "question", "language": "en"}))
        self.assertEqual(call.call_args.kwargs["stage"], "route_decision")

        answer_result = GeneratedAnswer(
            answer="answer",
            confidence=0.8,
            citation_ids=["chunk-1"],
            abstained=False,
        )
        state = {
            "query": "question",
            "language": "en",
            "route": "retrieve_docs",
            "retrieved_chunks": [
                {
                    "id": "chunk-1",
                    "document_id": "document-1",
                    "content": "evidence",
                    "title": "title",
                    "url": None,
                }
            ],
        }
        with patch.object(graph, "generate_structured", return_value=answer_result) as call:
            asyncio.run(graph.generate_node(state))
        self.assertEqual(call.call_args.kwargs["stage"], "answer_generation")

    def test_provider_failure_log_is_stage_aware_and_sanitized(self):
        secret = "GROQ_API_KEY=never-log-this"
        generated = "private generated answer"
        request = httpx.Request(
            "POST",
            "https://offline.invalid/openai/v1/chat/completions",
            headers={"Authorization": "Bearer never-log-this"},
        )
        response = httpx.Response(400, request=request)
        error = BadRequestError(
            f"unsafe message containing {secret} and {generated}",
            response=response,
            body={
                "error": {
                    "message": generated,
                    "type": "invalid_request_error",
                    "code": "tool_use_failed",
                    "failed_generation": "",
                }
            },
        )
        failing_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(parse=lambda **_: (_ for _ in ()).throw(error))
            )
        )

        with (
            self.assertLogs("app.agent.llm", level="ERROR") as captured,
            patch.object(llm, "_get_client", return_value=(failing_client, "groq")),
            self.assertRaises(LLMProviderError),
        ):
            llm.generate_structured(
                stage="answer_generation",
                system_prompt=f"prompt {secret}",
                user_prompt=generated,
                response_model=GeneratedAnswer,
            )

        logs = "\n".join(captured.output)
        self.assertIn("stage=answer_generation", logs)
        self.assertIn("exception_chain=BadRequestError", logs)
        self.assertIn("http_status=400", logs)
        self.assertIn("provider_error_type=invalid_request_error", logs)
        self.assertIn("provider_error_code=tool_use_failed", logs)
        self.assertIn("failed_generation_present=true", logs)
        self.assertIn("failed_generation_empty=true", logs)
        self.assertNotIn(secret, logs)
        self.assertNotIn(generated, logs)
        self.assertNotIn("Authorization", logs)

    def test_validation_diagnostics_include_only_locations_and_categories(self):
        secret = "private invalid value"
        try:
            GeneratedAnswer.model_validate(
                {
                    "answer": secret,
                    "confidence": 2,
                    "citation_ids": [],
                    "abstained": False,
                }
            )
        except ValidationError as validation_error:
            retry_error = RuntimeError("retry wrapper")
            retry_error.n_attempts = 4
            retry_error.failed_attempts = [
                SimpleNamespace(exception=validation_error)
            ]
        diagnostics = llm._exception_diagnostics(retry_error)
        self.assertEqual(diagnostics["attempt_count"], 4)
        self.assertIn("confidence:less_than_equal", diagnostics["validation_errors"])
        self.assertNotIn(secret, str(diagnostics))


class SafePublicMappingTests(unittest.TestCase):
    async def _healthy_session(self):
        yield SimpleNamespace(execute=AsyncMock())

    def test_provider_400_still_maps_to_safe_public_502(self):
        original_key = main.settings.setu_api_key
        original_limiter = security.query_rate_limiter
        main.settings.setu_api_key = SecretStr("offline-api-key")
        security.query_rate_limiter = security.InMemoryRateLimiter(100, 60)
        main.app.dependency_overrides[main.get_session] = self._healthy_session
        try:
            provider_error = LLMProviderError()
            provider_error.__cause__ = RuntimeError("internal provider detail")
            with (
                patch.object(main, "run_agent", AsyncMock(side_effect=provider_error)),
                TestClient(main.app) as client,
            ):
                response = client.post(
                    "/query",
                    json={"query": "offline question"},
                    headers={"X-API-Key": "offline-api-key"},
                )
        finally:
            main.app.dependency_overrides.clear()
            main.settings.setu_api_key = original_key
            security.query_rate_limiter = original_limiter

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "llm_provider_unavailable")
        self.assertNotIn("internal provider detail", response.text)


if __name__ == "__main__":
    unittest.main()
