import unittest
from uuid import UUID

from app import sources


class ScalarResult:
    def __init__(self, value): self.value = value
    def scalar_one(self): return self.value


class MappingRows:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def all(self): return self.rows
    def one_or_none(self): return self.rows[0] if self.rows else None


class RecordingSession:
    def __init__(self, results): self.results = iter(results); self.calls = []
    async def execute(self, statement, parameters): self.calls.append((str(statement), parameters)); return next(self.results)


class SourceQueryTests(unittest.IsolatedAsyncioTestCase):
    def test_query_text_is_read_only(self):
        for statement in (sources.LIST_SQL, sources.COUNT_SQL, sources.DETAIL_SQL, sources.ELIGIBILITY_SQL):
            normalized = str(statement).upper()
            self.assertIn("SELECT", normalized)
            for write in ("INSERT ", "UPDATE ", "DELETE ", "ALTER ", "DROP ", "GRANT "):
                self.assertNotIn(write, normalized)

    def test_search_is_escaped_and_pagination_is_bounded_by_caller_contract(self):
        self.assertEqual(sources._escape_search("%_'\\"), "%\\%\\_'\\\\%")

    def test_sanitizer_allows_only_explicit_metadata_and_flat_criteria(self):
        value = {"posted_on": "safe", "prid": 123, "raw_text": "body", "private": {"token": "x"}}
        self.assertEqual(sources._safe_mapping(value, sources.SAFE_METADATA_KEYS), {"posted_on": "safe", "prid": 123})

    async def test_list_uses_two_bounded_queries_without_writes(self):
        row = {"id": UUID("11111111-1111-1111-1111-111111111111"), "title": "Safe", "source": "PIB", "language": "en", "metadata": {"posted_on": "safe", "raw_text": "blocked"}, "chunk_count": 2, "eligibility_count": 0}
        session = RecordingSession([ScalarResult(1), MappingRows([row])])
        response = await sources.list_sources(session, page=2, page_size=5, search="title'; DROP TABLE documents;--", language="en", has_eligibility=None)
        self.assertEqual(response.total, 1); self.assertEqual(response.items[0].metadata, {"posted_on": "safe"}); self.assertEqual(session.calls[1][1]["limit"], 5); self.assertEqual(session.calls[1][1]["offset"], 5)

    async def test_detail_sanitizes_eligibility_criteria(self):
        row = {"id": UUID("11111111-1111-1111-1111-111111111111"), "title": "Safe", "source": "PIB", "language": "en", "metadata": {}, "chunk_count": 2, "eligibility_count": 1}
        criteria = {"min_age": 10, "description": "safe", "credential": "blocked", "nested": {"blocked": True}}
        session = RecordingSession([MappingRows([row]), MappingRows([{"scheme_name": "Scheme", "criteria": criteria}])])
        response = await sources.get_source(session, row["id"])
        self.assertEqual(response.eligibility[0].criteria, {"min_age": 10, "description": "safe"})


if __name__ == "__main__": unittest.main()
