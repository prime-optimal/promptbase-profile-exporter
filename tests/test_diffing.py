import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from promptbase_exporter.diffing import compare_catalogs, format_diff_report, load_catalog
from promptbase_exporter.formatting import write_export
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

    def test_load_catalog_round_trips_supported_export_formats(self):
        records = [
            record("Alpha", "Alpha description"),
            record("Beta", "Beta description"),
        ]
        with TemporaryDirectory() as directory:
            output_dir = Path(directory)
            for export_format in ("txt", "markdown", "json", "csv"):
                output_path = write_export(output_dir, "acb", "all", records, export_format)

                loaded = load_catalog(output_path)

                self.assertEqual([item["title"] for item in loaded], ["Alpha", "Beta"])
                self.assertEqual(
                    [item["description"] for item in loaded],
                    ["Alpha description", "Beta description"],
                )

    def test_load_text_catalog_ignores_header_like_description_lines(self):
        records = [
            record(
                "Alpha",
                "Alpha description\n5.\nStill part of Alpha.",
            )
        ]
        with TemporaryDirectory() as directory:
            output_path = write_export(Path(directory), "acb", "all", records, "txt")

            loaded = load_catalog(output_path)

        self.assertEqual(len(loaded), 1)
        self.assertIn("Still part of Alpha.", loaded[0]["description"])

    def test_load_markdown_catalog_ignores_header_like_description_lines(self):
        records = [
            record(
                "Alpha",
                "Alpha description\n\n## 5. Still part of Alpha\nMore details.",
            )
        ]
        with TemporaryDirectory() as directory:
            output_path = write_export(Path(directory), "acb", "all", records, "markdown")

            loaded = load_catalog(output_path)

        self.assertEqual(len(loaded), 1)
        self.assertIn("## 5. Still part of Alpha", loaded[0]["description"])


if __name__ == "__main__":
    unittest.main()
