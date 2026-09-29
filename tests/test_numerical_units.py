import unittest

from app.numerical_grounding import validate_numerical_grounding


class ReviewedAgeUnitTests(unittest.TestCase):
    def test_hindi_age_range_matches_cited_english_years(self):
        result = validate_numerical_grounding(
            "18 से 70 वर्ष आयु के व्यक्तिगत खाताधारक शामिल हो सकते हैं।",
            ["Individual account holders in the age group of 18 to 70 years."],
        )
        self.assertTrue(result.is_valid)

    def test_bengali_years_match_cited_english_years(self):
        self.assertTrue(validate_numerical_grounding("সর্বোচ্চ ৭০ বছর।", ["Maximum 70 years."]).is_valid)

    def test_wrong_number_or_unit_still_fails(self):
        for answer in ("71 वर्ष", "70 वर्षा", "70 वर्ष"):
            evidence = "70 years" if answer != "70 वर्ष" else "70 days"
            with self.subTest(answer=answer):
                self.assertFalse(validate_numerical_grounding(answer, [evidence]).is_valid)
