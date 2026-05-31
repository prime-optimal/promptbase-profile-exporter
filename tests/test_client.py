import unittest
from unittest.mock import patch

from promptbase_exporter.client import (
    PromptBaseError,
    _raise_if_schema_changed,
    _run_query_all,
    field_filter,
)


class PaginationTests(unittest.TestCase):
    def test_run_query_all_fetches_until_short_page(self):
        page_one = [{"slug": "a"}, {"slug": "b"}]
        page_two = [{"slug": "c"}]

        with patch(
            "promptbase_exporter.client._run_query",
            side_effect=[page_one, page_two],
        ) as query:
            docs = _run_query_all(
                "Items",
                [field_filter("uid", "EQUAL", {"stringValue": "uid-1"})],
                page_size=2,
            )

        self.assertEqual(docs, [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}])
        self.assertEqual(query.call_count, 2)
        self.assertEqual(query.call_args_list[0].kwargs["offset"], 0)
        self.assertEqual(query.call_args_list[1].kwargs["offset"], 2)


class SchemaDriftTests(unittest.TestCase):
    def test_raise_if_schema_changed_reports_missing_fields(self):
        with self.assertRaisesRegex(PromptBaseError, "missing expected field"):
            _raise_if_schema_changed(
                "Items",
                [{"slug": "a"}, {"slug": "b"}],
                {"slug", "title"},
            )

    def test_raise_if_schema_changed_allows_empty_results(self):
        _raise_if_schema_changed("Items", [], {"slug", "title"})


if __name__ == "__main__":
    unittest.main()
