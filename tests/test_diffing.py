import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from promptbase_exporter.diffing import compare_catalogs, format_diff_report, load_catalog
from promptbase_exporter.models import PromptRecord


def record(title, description, slug=None):
    return PromptRecord(
        title=title,
        description=description,
        slug=slug or title.lower().replace(" ", "-"),
        prompt_type="gpt",
        domain="text",
        created=1,
        price=0,
    )


class DiffingTests(unittest.TestCase):
    def test_load_text_catalog_and_compare_by_title_fallback(self):
        previous_text = (
            "1.\n"
            "Title: Alpha\n"
            "Description:\n"
            "Old description\n"
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "previous.txt"
            path.write_text(previous_text, encoding="utf-8")

            previous = load_catalog(path)

        diff = compare_catalogs(
            previous,
            [
                record("Alpha", "New description", slug="alpha-slug"),
                record("Beta", "Beta description"),
            ],
        )

        self.assertEqual(len(diff.added), 1)
        self.assertEqual(len(diff.changed), 1)
        self.assertEqual(diff.changed[0].fields, ("description",))

    def test_compare_json_catalog_by_slug(self):
        previous = [
            {
                "title": "Alpha",
                "description": "Same",
                "slug": "alpha",
                "type": "gpt",
                "domain": "text",
                "price": 0,
            }
        ]

        diff = compare_catalogs(previous, [record("Alpha Renamed", "Same", slug="alpha")])

        self.assertEqual(len(diff.added), 0)
        self.assertEqual(len(diff.removed), 0)
        self.assertEqual(diff.changed[0].fields, ("title",))

    def test_format_diff_report_contains_summary(self):
        diff = compare_catalogs([], [record("Alpha", "Description")])

        report = format_diff_report(diff)

        self.assertIn("# PromptBase Catalog Diff", report)
        self.assertIn("- Added: 1", report)
        self.assertIn("## Added", report)


if __name__ == "__main__":
    unittest.main()
