"""Provenance gate for data/traffic_offences.

Every offence row must cite a source URL, a notification reference and an
effective date. A state amount may exist only under a verified s.200
notification; anything else stays empty and UNVERIFIED.
"""

import copy
import datetime as dt
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "traffic_offences"
SCHEMA = json.loads((DATA_DIR / "schema.json").read_text(encoding="utf-8"))
STATE_FILES = sorted(path for path in DATA_DIR.glob("*.json") if path.name != "schema.json")
REQUIRED_OFFENCES = {"helmet", "phone_device", "no_licence", "no_insurance", "overspeeding", "red_light", "triple_riding"}


def _schema_errors(value, schema, path="$"):
    """Validate the JSON Schema subset used by schema.json (no third-party dependency)."""
    if "$ref" in schema:
        schema = SCHEMA["$defs"][schema["$ref"].rsplit("/", 1)[-1]]
    errors = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return errors + [f"{path}: expected object"]
        errors += [f"{path}: missing {key}" for key in schema.get("required", []) if key not in value]
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: too few properties")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors += _schema_errors(item, properties[key], f"{path}.{key}")
            elif extra is False:
                errors.append(f"{path}: unexpected key {key}")
            elif isinstance(extra, dict):
                errors += _schema_errors(item, extra, f"{path}.{key}")
    elif kind == "array":
        if not isinstance(value, list):
            return errors + [f"{path}: expected array"]
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        for index, item in enumerate(value):
            errors += _schema_errors(item, schema.get("items", {}), f"{path}[{index}]")
    elif kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool) or value < schema.get("minimum", value):
            errors.append(f"{path}: expected integer >= {schema.get('minimum')}")
    elif kind == "string" or "pattern" in schema or "minLength" in schema:
        if not isinstance(value, str):
            return errors + [f"{path}: expected string"]
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: empty string")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match {schema['pattern']}")
    return errors


def _date(value):
    return dt.date.fromisoformat(value)


def provenance_errors(table: dict) -> list[str]:
    errors = _schema_errors(table, SCHEMA)
    if errors:
        return errors
    sources = table["sources"]
    retrieved = _date(table["retrieved_at"])

    def cited(source_id, where):
        source = sources.get(source_id)
        if source is None:
            errors.append(f"{where}: unknown source {source_id!r}")
            return None
        for field in ("url", "notification_reference", "sha256"):
            if not source.get(field):
                errors.append(f"{where}: source {source_id} lacks {field}")
        if _date(source["retrieved_at"]) > retrieved:
            errors.append(f"{where}: source {source_id} retrieved after the table date")
        return source

    ids = [offence["offence_id"] for offence in table["offences"]]
    if set(ids) != REQUIRED_OFFENCES or len(ids) != len(set(ids)):
        errors.append(f"offence set must be exactly {sorted(REQUIRED_OFFENCES)}, got {ids}")

    for offence in table["offences"]:
        where = offence["offence_id"]
        law = offence["central_law"]
        cited(law["source_id"], f"{where}.central_law")
        if "commencement_source_id" in law:
            cited(law["commencement_source_id"], f"{where}.central_law")
        if _date(law["effective_from"]) > retrieved:
            errors.append(f"{where}: central effective date is after retrieval")

        state = offence["state_compounding"]
        if state["status"] == "VERIFIED":
            if not state["amounts"]:
                errors.append(f"{where}: VERIFIED row has no amounts")
            for field in ("source_id", "schedule_row", "effective_from"):
                if not state.get(field):
                    errors.append(f"{where}: VERIFIED row lacks {field}")
            source = cited(state.get("source_id"), f"{where}.state_compounding")
            if source and source["kind"] != "state_s200_notification":
                errors.append(f"{where}: state amount cites {source['kind']}, not a s.200 notification")
            if state.get("effective_from") and _date(state["effective_from"]) > retrieved:
                errors.append(f"{where}: state effective date is after retrieval")
            if state.get("effective_to") and state.get("effective_from") and state["effective_to"] <= state["effective_from"]:
                errors.append(f"{where}: effective_to must be after effective_from")
        else:
            if state["amounts"]:
                errors.append(f"{where}: UNVERIFIED row must not carry amounts")
            if not state.get("settle_with"):
                errors.append(f"{where}: UNVERIFIED row must say what source would settle it")
            if state.get("source_id"):
                errors.append(f"{where}: UNVERIFIED row must not cite an amount source")

        for observation in offence["observations"]:
            cited(observation["source_id"], f"{where}.observations")
    return errors


class TrafficOffenceProvenanceTests(unittest.TestCase):
    def test_one_file_per_required_state(self):
        self.assertEqual({path.stem for path in STATE_FILES}, {"WB", "KA", "DL"})

    def test_state_files_pass_schema_and_provenance_rules(self):
        for path in STATE_FILES:
            with self.subTest(state=path.stem):
                table = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(provenance_errors(table), [])
                self.assertEqual(table["jurisdiction"], f"IN-{path.stem}")

    def test_every_offence_row_has_source_url_notification_and_effective_date(self):
        for path in STATE_FILES:
            table = json.loads(path.read_text(encoding="utf-8"))
            for offence in table["offences"]:
                with self.subTest(state=path.stem, offence=offence["offence_id"]):
                    source = table["sources"][offence["central_law"]["source_id"]]
                    self.assertTrue(source["url"].startswith("https://"))
                    self.assertTrue(source["notification_reference"])
                    self.assertTrue(offence["central_law"]["effective_from"])

    def test_no_amount_without_verified_state_notification(self):
        for path in STATE_FILES:
            table = json.loads(path.read_text(encoding="utf-8"))
            for offence in table["offences"]:
                state = offence["state_compounding"]
                if state["amounts"]:
                    with self.subTest(state=path.stem, offence=offence["offence_id"]):
                        self.assertEqual(state["status"], "VERIFIED")
                        self.assertEqual(table["sources"][state["source_id"]]["kind"], "state_s200_notification")

    def test_delhi_has_no_verified_amounts(self):
        table = json.loads((DATA_DIR / "DL.json").read_text(encoding="utf-8"))
        self.assertTrue(all(o["state_compounding"]["status"] == "UNVERIFIED" for o in table["offences"]))


class ProvenanceGateRejectsBadRowsTests(unittest.TestCase):
    """Prove the gate fails closed on each required field."""

    def setUp(self):
        self.table = json.loads((DATA_DIR / "WB.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance_errors(self.table), [])

    def _mutated(self, mutate):
        table = copy.deepcopy(self.table)
        mutate(table)
        return provenance_errors(table)

    def test_missing_source_url_fails(self):
        self.assertTrue(self._mutated(lambda t: t["sources"]["WB-208-WT-2022"].pop("url")))

    def test_non_https_source_url_fails(self):
        self.assertTrue(self._mutated(lambda t: t["sources"]["WB-208-WT-2022"].update(url="http://example.invalid")))

    def test_missing_notification_reference_fails(self):
        self.assertTrue(self._mutated(lambda t: t["sources"]["IN-ACT-32-2019"].pop("notification_reference")))

    def test_missing_central_effective_date_fails(self):
        self.assertTrue(self._mutated(lambda t: t["offences"][0]["central_law"].pop("effective_from")))

    def test_missing_state_effective_date_fails(self):
        self.assertTrue(self._mutated(lambda t: t["offences"][0]["state_compounding"].pop("effective_from")))

    def test_amount_on_unverified_row_fails(self):
        def mutate(table):
            state = next(o for o in table["offences"] if o["offence_id"] == "red_light")["state_compounding"]
            state["amounts"] = [{"occurrence": "first", "vehicle_class": "any", "inr": 500}]
        self.assertTrue(self._mutated(mutate))

    def test_amount_sourced_from_police_schedule_fails(self):
        self.assertTrue(self._mutated(lambda t: t["offences"][0]["state_compounding"].update(source_id="KP-OFFENCES-2024")))

    def test_unknown_source_fails(self):
        self.assertTrue(self._mutated(lambda t: t["offences"][0]["central_law"].update(source_id="MISSING")))


if __name__ == "__main__":
    unittest.main()
