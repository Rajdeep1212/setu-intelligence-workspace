"""Phase 3: deterministic premise checks for traffic-fine questions.

Offline tests. No provider, database or network is used; the agent tests
patch the model call and fail if it is ever reached for a traffic question.
"""

import asyncio
import re
import unittest
from datetime import date
from unittest.mock import patch

from app.agent import graph
from app.agent.premise import (
    check_premise,
    extract_facts,
    find_claimed_amounts,
    find_year,
    load_table,
    missing_facts,
)
from app.agent.premise_answer import compose, format_inr
from app.schemas import QueryResponse
from eval import premise_evaluation, temporal_evaluation


def _no_model(*_args, **_kwargs):
    raise AssertionError("a traffic-fine question must not reach the model")


class ExtractionTests(unittest.TestCase):
    def test_amounts_in_three_scripts_and_number_words(self):
        cases = {
            "Police want ₹5,000": (5000,),
            "Rs. 500 challan": (500,),
            "Police want 10k for this": (10000,),
            "two lakh rupees": (200000,),
            "पांच हज़ार रुपये": (5000,),
            "₹२००० जुर्माना": (2000,),
            "১০০০ টাকা জরিমানা": (1000,),
            "challan 3000 hai kya": (3000,),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(find_claimed_amounts(text), expected)

    def test_years_counts_and_section_numbers_are_not_amounts(self):
        for text in ("What was the fine in 2019?", "three people on a bike", "Act 32 of 2019 fine", "section 184 fine"):
            with self.subTest(text=text):
                self.assertEqual(find_claimed_amounts(text), ())

    def test_years_are_found_but_not_confused_with_amounts(self):
        self.assertEqual(find_year("helmet fine in Kolkata in 2020"), 2020)
        self.assertEqual(find_year("২০২০ সালে জরিমানা"), 2020)
        self.assertIsNone(find_year("Police want ₹2,000"))

    def test_earphones_are_not_treated_as_phone_use(self):
        self.assertEqual(extract_facts("Earphone fine in Kolkata is ₹10,000?").offences, ("earphones",))

    def test_non_traffic_questions_do_not_trigger(self):
        for query in (
            "How do I link my mobile phone number to Aadhaar?",
            "How do I pay my car insurance premium of ₹4,000 online?",
            "What is the fee to renew a driving licence in Karnataka, is it Rs 200?",
            "आधार से मोबाइल नंबर कैसे जोड़ें?",
        ):
            with self.subTest(query=query):
                self.assertFalse(extract_facts(query).is_fine_question)
                self.assertEqual(missing_facts(query), [])


class VerdictSafetyTests(unittest.TestCase):
    def test_red_light_is_never_confirmed_or_contradicted(self):
        for code in ("IN-WB", "IN-KA", "IN-DL"):
            result = check_premise("Red light fine in Kolkata is Rs 500?", load_table(code))
            self.assertEqual(result["verdict"], "legal_review")
            self.assertEqual(result["verified_amounts"], [])

    def test_unverified_rows_never_contradict(self):
        result = check_premise("Delhi police say the helmet fine is ₹25,000", load_table("IN-DL"))
        self.assertEqual(result["verdict"], "unverified")

    def test_amount_not_in_force_on_the_date_is_never_quoted(self):
        table = load_table("IN-WB")  # WB notification in force from 24 Jan 2022
        self.assertEqual(check_premise("Helmet fine in Kolkata in 2020?", table)["verdict"], "not_in_force")
        self.assertEqual(check_premise("Helmet fine in Kolkata?", table, as_of=date(2022, 1, 23))["verdict"], "not_in_force")
        self.assertEqual(check_premise("Helmet fine in Kolkata?", table, as_of=date(2022, 1, 24))["verdict"], "no_claim")

    def test_supported_and_contradicted(self):
        table = load_table("IN-WB")
        self.assertEqual(check_premise("Kolkata police asked Rs 5,000 for phone use, first offence", table)["verdict"], "supported")
        self.assertEqual(check_premise("Kolkata police asked Rs 10,000 for phone use, first offence", table)["verdict"], "contradicted")
        self.assertEqual(check_premise("Kolkata police asked Rs 10,000 for phone use, second time", table)["verdict"], "supported")


class EvaluationSuiteTests(unittest.TestCase):
    def test_development_and_holdout_sets_pass(self):
        for path in ("premise_cases.jsonl", "premise_holdout.jsonl"):
            with self.subTest(path=path), patch.object(premise_evaluation, "CASES_PATH", premise_evaluation.ROOT / "eval" / path):
                report, success = premise_evaluation.evaluate()
                self.assertTrue(success, report["failures"])
                self.assertEqual(report["accepted_false_premises"], [])
                self.assertEqual(report["over_ask"]["asked_anyway"], [])
                self.assertEqual(report["false_triggers"]["triggered"], [])

    def test_all_fifteen_temporal_cases_pass(self):
        report, success = temporal_evaluation.evaluate()
        self.assertTrue(success, report["unexpected"])
        self.assertEqual(report["outcomes"], {"pass": 15})


class AnswerTests(unittest.TestCase):
    def test_indian_digit_grouping(self):
        self.assertEqual(format_inr(500), "₹500")
        self.assertEqual(format_inr(10000), "₹10,000")
        self.assertEqual(format_inr(200000), "₹2,00,000")

    def test_contradicted_claim_states_the_notification_and_calm_guidance(self):
        query = "Kolkata police say the helmet fine is ₹5,000. Is that right?"
        update = compose(query, extract_facts(query), "en")
        self.assertEqual(update["response_status"], "rule_lookup")
        self.assertIn("₹1,000", update["answer"])
        self.assertIn("208-WT", update["answer"])
        self.assertIn("₹5,000 does not match", update["answer"])
        self.assertIn("e-challan", update["answer"])
        self.assertIn("Not legal advice", update["answer"])

    def test_missing_place_asks_instead_of_guessing(self):
        for query, language in (
            ("What is the fine for riding without a helmet?", "en"),
            ("गाड़ी चलाते समय मोबाइल फ़ोन इस्तेमाल करने पर कितना जुर्माना है?", "hi"),
            ("বিমা ছাড়া গাড়ি চালালে কত জরিমানা?", "bn"),
        ):
            with self.subTest(language=language):
                update = compose(query, extract_facts(query), language)
                self.assertEqual(update["response_status"], "needs_clarification")
                self.assertNotRegex(update["answer"], r"₹")

    def test_request_jurisdiction_fills_a_missing_place(self):
        query = "What is the fine for riding without a helmet?"
        update = compose(query, extract_facts(query), "en", requested_jurisdiction="IN-KA")
        self.assertEqual(update["response_status"], "rule_lookup")
        self.assertIn("₹500", update["answer"])

    def test_answers_are_in_the_question_language(self):
        for query, language, script in (
            ("कोलकाता पुलिस कहती है कि हेलमेट का जुर्माना ₹5,000 है", "hi", r"[ऀ-ॿ]"),
            ("কলকাতা পুলিশ বলছে হেলমেট ছাড়া ৫০০০ টাকা জরিমানা", "bn", r"[ঀ-৿]"),
        ):
            with self.subTest(language=language):
                answer = compose(query, extract_facts(query), language)["answer"]
                self.assertRegex(answer, script)

    def test_no_answer_ever_coaches_confrontation(self):
        queries = [case["query"] for case in premise_evaluation.load_cases()]
        for query in queries:
            facts = extract_facts(query)
            if not facts.is_fine_question:
                continue
            for language in ("en", "hi", "bn"):
                answer = compose(query, facts, language)["answer"]
                self.assertNotRegex(answer, re.compile(r"\b(refuse|argue|bribe|officer is wrong|don't pay)\b", re.I))

    def test_response_validates_against_the_api_schema(self):
        query = "Kolkata police say the helmet fine is ₹5,000. Is that right?"
        update = compose(query, extract_facts(query), "en")
        response = QueryResponse(
            answer=update["answer"],
            citations=[],
            sections=update["sections"],
            route=update["route"],
            response_status=update["response_status"],
            premise_check=update["premise_check"],
        )
        self.assertEqual(response.premise_check.verdict, "contradicted")


class AgentGateTests(unittest.TestCase):
    def test_traffic_question_is_answered_without_the_model_or_retrieval(self):
        with (
            patch.object(graph, "generate_structured", side_effect=_no_model),
            patch.object(graph, "retrieve_docs_tool", side_effect=_no_model),
        ):
            state = asyncio.run(graph.run_agent(object(), "Kolkata police say the helmet fine is ₹5,000. Is that right?"))
        self.assertEqual(state["route"], "traffic_rules")
        self.assertEqual(state["premise_check"]["verdict"], "contradicted")

    def test_request_date_is_respected(self):
        with patch.object(graph, "generate_structured", side_effect=_no_model):
            state = asyncio.run(
                graph.run_agent(object(), "Helmet fine in Kolkata?", jurisdiction="IN-WB", as_of=date(2021, 6, 1))
            )
        self.assertEqual(state["premise_check"]["verdict"], "not_in_force")
        self.assertNotIn("₹", state["answer"])


if __name__ == "__main__":
    unittest.main()
