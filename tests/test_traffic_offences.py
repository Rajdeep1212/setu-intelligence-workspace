import copy
import json
import tempfile
import unittest
from pathlib import Path

from app.traffic_offences import (
    DEFAULT_TABLE_DIR,
    OFFICIAL_STATUSES,
    is_official_url,
    jurisdiction_chain,
    load_tables,
    lookup,
    validate_table,
)


def _read(name: str) -> dict:
    return json.loads((DEFAULT_TABLE_DIR / f"{name}.json").read_text(encoding="utf-8"))


class TrafficOffenceTableTests(unittest.TestCase):
    def test_every_table_is_valid(self):
        tables = load_tables()
        self.assertEqual(set(tables), {"IN", "IN-WB", "IN-WB-KOL", "IN-KA", "IN-DL"})

    def test_no_amount_without_a_source(self):
        for table in load_tables().values():
            for row in table["offences"]:
                has_amount = row["first_offence"] is not None or row["subsequent_offence"] is not None
                if has_amount:
                    self.assertIsNotNone(row["source"], row["offence_id"])
                    self.assertTrue(row["source"]["url"].startswith("https://"))
                    self.assertTrue(row["source"]["date"])

    def test_official_statuses_use_official_hosts(self):
        for table in load_tables().values():
            for row in table["offences"]:
                if row["status"] in OFFICIAL_STATUSES:
                    self.assertTrue(is_official_url(row["source"]["url"]), row["offence_id"])

    def test_unverified_states_carry_no_amounts(self):
        for code in ("IN-KA", "IN-DL"):
            for row in _read(code)["offences"]:
                self.assertEqual(row["status"], "UNVERIFIED")
                self.assertIsNone(row["first_offence"])
                self.assertIsNone(row["subsequent_offence"])

    def test_kolkata_earphone_values_match_published_list(self):
        row = lookup(load_tables(), "IN-WB-KOL", "earphone_use")
        self.assertEqual(row["jurisdiction"], "IN-WB-KOL")
        self.assertEqual(row["first_offence"], {"min": 5000, "max": 5000})
        self.assertEqual(row["subsequent_offence"], {"min": 10000, "max": 10000})
        self.assertEqual(row["sections"], ["184"])


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.table = _read("IN-WB-KOL")

    def _errors_after(self, change) -> list[str]:
        table = copy.deepcopy(self.table)
        change(table["offences"][0])
        return validate_table(table, expected_jurisdiction="IN-WB-KOL")

    def test_rejects_amount_on_unverified_row(self):
        def change(row):
            row["status"] = "UNVERIFIED"

        self.assertTrue(any("must not carry amounts" in e for e in self._errors_after(change)))

    def test_rejects_missing_source(self):
        def change(row):
            row["source"] = None

        self.assertTrue(any("source: required" in e for e in self._errors_after(change)))

    def test_rejects_official_status_on_unofficial_host(self):
        def change(row):
            row["source"]["url"] = "https://example.com/fines"

        self.assertTrue(any("needs an official host" in e for e in self._errors_after(change)))

    def test_rejects_notification_date_without_reference(self):
        def change(row):
            row["source"]["date_kind"] = "notification_date"
            row["source"]["notification_ref"] = None

        self.assertTrue(any("notification_ref" in e for e in self._errors_after(change)))

    def test_rejects_min_above_max(self):
        def change(row):
            row["first_offence"] = {"min": 6000, "max": 5000}

        self.assertTrue(any("min is greater than max" in e for e in self._errors_after(change)))

    def test_rejects_file_name_mismatch(self):
        errors = validate_table(self.table, expected_jurisdiction="IN-DL")
        self.assertTrue(any("does not match file name" in e for e in errors))

    def test_load_tables_raises_on_invalid_file(self):
        broken = copy.deepcopy(self.table)
        broken["offences"][0]["source"] = None
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "IN-WB-KOL.json").write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_tables(Path(tmp))


class LookupTests(unittest.TestCase):
    def test_jurisdiction_chain_is_most_specific_first(self):
        self.assertEqual(jurisdiction_chain("IN-WB-KOL"), ["IN-WB-KOL", "IN-WB", "IN"])
        self.assertEqual(jurisdiction_chain("IN"), ["IN"])

    def test_falls_back_to_a_confirmed_broader_value(self):
        row = lookup(load_tables(), "IN-WB-KOL", "handheld_device_use")
        self.assertEqual(row["jurisdiction"], "IN")
        self.assertEqual(row["status"], "SECONDARY")

    def test_returns_unverified_row_when_nothing_is_confirmed(self):
        row = lookup(load_tables(), "IN-KA", "triple_riding")
        self.assertEqual(row["status"], "UNVERIFIED")
        self.assertIsNone(row["first_offence"])

    def test_unknown_offence_returns_none(self):
        self.assertIsNone(lookup(load_tables(), "IN-WB", "not_an_offence"))

    def test_official_url_rules(self):
        self.assertTrue(is_official_url("https://www.kolkatatrafficpolice.gov.in/offences.pdf"))
        self.assertTrue(is_official_url("https://www.wbtrafficpolice.com/offences-and-penalties.php"))
        self.assertFalse(is_official_url("http://www.kolkatatrafficpolice.gov.in/offences.pdf"))
        self.assertFalse(is_official_url("https://gov.in.example.com/"))
        self.assertFalse(is_official_url("https://parivahan-gov.in.example.org/"))


if __name__ == "__main__":
    unittest.main()
