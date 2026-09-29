"""Phase 4a: Scam Shield checks pasted messages and links with fixed rules.

Offline tests. No provider, database or network is used; the agent tests
patch the model call and retrieval, and fail if either is ever reached for a
screened message.
"""

import asyncio
import json
import re
import unittest
from unittest.mock import patch

from app.agent import graph
from app.agent.scam_shield import (
    MAX_SECTIONS,
    SOURCES_PATH,
    TEXT,
    check_message,
    compose,
    extract_links,
    is_official_host,
    should_check,
)
from app.schemas import QueryResponse
from eval import scam_evaluation


def _no_model(*_args, **_kwargs):
    raise AssertionError("a screened message must not reach the model or retrieval")


class DomainRuleTests(unittest.TestCase):
    def test_only_gov_in_and_nic_in_hosts_are_official(self):
        for host in ("echallan.parivahan.gov.in", "cybercrime.gov.in", "www.nic.in", "parivahan.gov.in"):
            with self.subTest(host=host):
                self.assertTrue(is_official_host(host))
        for host in (
            "echallan-parivahan.online",
            "parivahan.gov.in.pay-now.xyz",
            "gov.in.example.com",
            "fakegov.in",
            "parivahan-gov.in",
        ):
            with self.subTest(host=host):
                self.assertFalse(is_official_host(host))

    def test_links_without_scheme_are_found(self):
        self.assertIn("bit.ly/3xYzAb", " ".join(extract_links("pay now bit.ly/3xYzAb")))

    def test_look_alike_domain_is_a_likely_scam(self):
        report = check_message("Challan pending. Pay: https://echallan-parivahan.online/pay")
        self.assertEqual(report.verdict, "likely_scam")
        self.assertIn("impersonating_domain", report.signals)


class VerdictSafetyTests(unittest.TestCase):
    def test_no_answer_ever_calls_a_message_safe(self):
        texts = [case["text"] for path in ("scam_cases.jsonl", "scam_holdout.jsonl")
                 for case in scam_evaluation.load_cases(scam_evaluation.ROOT / "eval" / path)]
        for text in texts:
            if not should_check(text):
                continue
            for language in ("en", "hi", "bn"):
                answer = compose(text, language)["answer"]
                with self.subTest(text=text[:40], language=language):
                    self.assertNotRegex(answer, re.compile(r"\b(is safe|safe to|100%|guaranteed)\b", re.I))
                    self.assertNotIn("सुरक्षित है", answer)
                    self.assertNotIn("নিরাপদ", answer)

    def test_genuine_official_challan_message_is_not_a_scam(self):
        text = "Your challan no. WB123 has been generated. Check and pay only at https://echallan.parivahan.gov.in"
        report = check_message(text)
        self.assertEqual(report.verdict, "official_link")
        # The PIB warning about fake challan links is shown as context, not as a risk.
        self.assertNotIn("matches_debunk", report.signals)
        self.assertTrue(report.debunks)

    def test_false_claim_debunk_is_a_risk_on_its_own(self):
        report = check_message("Free laptop scheme 2026 for students, register with your Aadhaar details today")
        self.assertIn("matches_debunk", report.signals)
        self.assertEqual(report.verdict, "likely_scam")

    def test_asking_for_an_otp_is_high_risk(self):
        self.assertEqual(check_message("Share the OTP sent to your phone to clear the challan").verdict, "likely_scam")

    def test_personal_upi_id_for_a_fine_is_high_risk(self):
        report = check_message("Pay your traffic fine of Rs 1000 to rtoofficer@ybl today")
        self.assertIn("payment_to_personal_upi", report.signals)
        self.assertEqual(report.verdict, "likely_scam")


class TriggerTests(unittest.TestCase):
    def test_ordinary_questions_are_not_screened(self):
        for query in (
            "What is the helmet fine in Kolkata?",
            "Who is eligible for PM-KISAN?",
            "पीएम किसान योजना क्या है?",
            "Police asked ₹5,000 for no helmet in Kolkata, is that right?",
        ):
            with self.subTest(query=query):
                self.assertFalse(should_check(query))


class EvaluationSuiteTests(unittest.TestCase):
    def test_development_and_holdout_sets_pass(self):
        for name in ("scam_cases.jsonl", "scam_holdout.jsonl"):
            with self.subTest(path=name):
                report, success = scam_evaluation.evaluate(scam_evaluation.ROOT / "eval" / name)
                self.assertTrue(success, report["failures"])
                self.assertEqual(report["missed_scams"], [])
                self.assertEqual(report["false_alarms_on_genuine"], [])

    def test_every_debunk_cites_a_source_and_a_kind(self):
        data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
        for debunk in data["debunks"]:
            with self.subTest(debunk=debunk["id"]):
                self.assertTrue(debunk["source"].startswith("https://"))
                self.assertIn(debunk["kind"], ("false_claim", "channel_warning"))
                self.assertRegex(debunk["date"], r"^\d{4}-\d{2}-\d{2}$")


class AnswerTests(unittest.TestCase):
    def test_every_language_has_every_message(self):
        self.assertEqual(set(TEXT["en"]), set(TEXT["hi"]))
        self.assertEqual(set(TEXT["en"]), set(TEXT["bn"]))

    def test_advice_points_to_official_channels(self):
        answer = compose("Your challan is pending, pay now bit.ly/3xYzAb", "en")["answer"]
        for expected in ("1930", "cybercrime.gov.in", "echallan.parivahan.gov.in"):
            self.assertIn(expected, answer)

    def test_worst_case_message_fits_the_api(self):
        text = (
            "URGENT: your challan is pending, licence will be suspended today. Pay at http://bit.ly/x "
            "or http://192.168.1.4/pay or http://xn--parivahn-9za.com, install echallan.apk, share OTP "
            "and PIN, send to rto.fine@ybl. Free laptop scheme and PM-KUSUM registration fee also due."
        )
        update = compose(text, "en")
        self.assertLessEqual(len(update["sections"]), MAX_SECTIONS)
        self.assertEqual(" ".join(section["text"] for section in update["sections"]), update["answer"])
        response = QueryResponse(
            answer=update["answer"],
            sections=update["sections"],
            route=update["route"],
            response_status=update["response_status"],
            scam_check=update["scam_check"],
        )
        self.assertEqual(response.scam_check.verdict, "likely_scam")


class AgentGateTests(unittest.TestCase):
    def test_message_is_screened_without_the_model_or_retrieval(self):
        with (
            patch.object(graph, "generate_structured", side_effect=_no_model),
            patch.object(graph, "retrieve_docs_tool", side_effect=_no_model),
        ):
            state = asyncio.run(graph.run_agent(object(), "Your e-challan is pending, pay now bit.ly/3xYzAb"))
        self.assertEqual(state["route"], "scam_check")
        self.assertEqual(state["response_status"], "scam_check")
        self.assertEqual(state["scam_check"]["verdict"], "likely_scam")

    def test_scam_gate_runs_before_the_premise_gate(self):
        # This message also names an offence and an amount; it must be
        # treated as a message to check, not as a fine question.
        query = "Kolkata traffic police: helmet fine Rs 1000 pending, pay at https://wb-challan.in/pay"
        with patch.object(graph, "generate_structured", side_effect=_no_model):
            state = asyncio.run(graph.run_agent(object(), query))
        self.assertEqual(state["route"], "scam_check")
        self.assertNotIn("premise_check", state)

    def test_fine_questions_still_reach_the_premise_gate(self):
        with patch.object(graph, "generate_structured", side_effect=_no_model):
            state = asyncio.run(graph.run_agent(object(), "Kolkata police say the helmet fine is ₹5,000. Is that right?"))
        self.assertEqual(state["route"], "traffic_rules")
        self.assertNotIn("scam_check", state)


if __name__ == "__main__":
    unittest.main()
