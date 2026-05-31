import unittest
from unittest.mock import patch

from promptbase_exporter.client import (
    PromptBaseError,
    _raise_if_schema_changed,
    _run_query_all,
    fetch_prompts,
    field_filter,
    resolve_profile,
)
from promptbase_exporter.models import Profile


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

    def test_run_query_all_uses_cursor_for_ordered_pages(self):
        page_one = [
            {
                "slug": "a",
                "created": 3,
                "_doc_name": "projects/p/databases/(default)/documents/Items/a",
            },
            {
                "slug": "b",
                "created": 2,
                "_doc_name": "projects/p/databases/(default)/documents/Items/b",
            },
        ]
        page_two = [
            {
                "slug": "c",
                "created": 1,
                "_doc_name": "projects/p/databases/(default)/documents/Items/c",
            }
        ]
        order_by = [
            {"field": {"fieldPath": "created"}, "direction": "DESCENDING"},
            {"field": {"fieldPath": "__name__"}, "direction": "DESCENDING"},
        ]
        calls = []

        def query(*_args, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                self.assertIsNone(kwargs["start_after"])
                return page_one
            self.assertEqual(
                kwargs["start_after"],
                [
                    {"integerValue": "2"},
                    {
                        "referenceValue": (
                            "projects/p/databases/(default)/documents/Items/b"
                        )
                    },
                ],
            )
            return page_two

        with patch("promptbase_exporter.client._run_query", side_effect=query):
            docs = _run_query_all(
                "Items",
                [field_filter("uid", "EQUAL", {"stringValue": "uid-1"})],
                order_by=order_by,
                page_size=2,
            )

        self.assertEqual([doc["slug"] for doc in docs], ["a", "b", "c"])


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

    def test_raise_if_schema_changed_reports_majority_missing_required_field(self):
        docs = [{"slug": "one", "title": "One"}] + [
            {"slug": f"missing-{index}"} for index in range(9)
        ]

        with self.assertRaisesRegex(PromptBaseError, "missing expected field"):
            _raise_if_schema_changed("Items", docs, {"slug", "title"})

    def test_raise_if_schema_changed_tolerates_isolated_missing_required_field(self):
        docs = [{"slug": "missing-title"}] + [
            {"slug": f"ok-{index}", "title": "Title"} for index in range(9)
        ]

        _raise_if_schema_changed("Items", docs, {"slug", "title"})

    def test_raise_if_schema_changed_ignores_optional_fields(self):
        _raise_if_schema_changed(
            "Items",
            [{"slug": "one"}, {"slug": "two"}],
            {"slug"},
        )


class FetchPromptTests(unittest.TestCase):
    def test_fetch_prompts_normalizes_domain_case(self):
        with patch(
            "promptbase_exporter.client.resolve_profile",
            return_value=Profile(username="acb", uid="uid-1"),
        ), patch(
            "promptbase_exporter.client.fetch_prompt_items",
            return_value=[
                {
                    "slug": "text-one",
                    "title": "Text One",
                    "type": "gpt",
                    "domain": "Text",
                    "created": 1,
                },
                {
                    "slug": "image-one",
                    "title": "Image One",
                    "type": "chatgpt-image",
                    "domain": "IMAGE",
                    "created": 1,
                },
            ],
        ), patch(
            "promptbase_exporter.client.fetch_prompt_details",
            return_value={
                "text-one": {"description": "Text description"},
                "image-one": {"description": "Image description"},
            },
        ):
            _profile, records = fetch_prompts("@acb")

        self.assertEqual([record.domain for record in records], ["text", "image"])
        self.assertEqual(sum(record.is_text for record in records), 1)
        self.assertEqual(sum(record.is_image for record in records), 1)


class ResolveProfileTests(unittest.TestCase):
    def test_resolve_profile_rejects_ambiguous_profile_uids(self):
        with patch(
            "promptbase_exporter.client._run_query",
            return_value=[
                {"username": "acb", "uid": "uid-1"},
                {"username": "acb", "uid": "uid-2"},
            ],
        ):
            with self.assertRaisesRegex(PromptBaseError, "Ambiguous profile"):
                resolve_profile("@acb")


if __name__ == "__main__":
    unittest.main()
