import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from promptbase_exporter.formatting import (
    count_written_records,
    filter_records,
    filter_records_by_metadata,
    format_records_as_csv,
    format_records_as_json,
    format_records_as_markdown,
    format_records_as_text,
    sorted_newest_to_oldest,
    write_export,
)
from promptbase_exporter.models import PromptRecord


def record(title, domain, created, price=0.0, prompt_type=None):
    return PromptRecord(
        title=title,
        description=f"{title} description",
        slug=title.lower().replace(" ", "-"),
        prompt_type=prompt_type or ("gpt" if domain == "text" else "chatgpt-image"),
        domain=domain,
        created=created,
        price=price,
    )


class FormattingTests(unittest.TestCase):
    def test_filter_records(self):
        records = [
            record("Text One", "text", 3),
            record("Image One", "image", 2),
            record("Video One", "video", 1),
        ]

        self.assertEqual(len(filter_records(records, "all")), 3)
        self.assertEqual([r.title for r in filter_records(records, "text")], ["Text One"])
        self.assertEqual([r.title for r in filter_records(records, "image")], ["Image One"])

    def test_filter_records_by_metadata(self):
        records = [
            record("Free GPT", "text", 4, price=0, prompt_type="gpt"),
            record("Paid Claude", "text", 3, price=4.99, prompt_type="claude"),
            record("Paid Image", "image", 2, price=2.99, prompt_type="chatgpt-image"),
            record("Video", "video", 1, price=9.99, prompt_type="sora"),
        ]

        filtered = filter_records_by_metadata(
            records,
            domains={"text"},
            prompt_types={"claude"},
            paid_only=True,
            min_price=4,
            max_price=5,
        )

        self.assertEqual([r.title for r in filtered], ["Paid Claude"])
        self.assertEqual([r.title for r in filter_records_by_metadata(records, free_only=True)], ["Free GPT"])

    def test_format_records_as_text(self):
        text = format_records_as_text([record("Text One", "text", 1)])

        self.assertIn("1.\nTitle: Text One\nDescription:\nText One description", text)

    def test_format_records_as_markdown(self):
        text = format_records_as_markdown([record("Text One", "text", 1)])

        self.assertIn("# PromptBase Prompt Export", text)
        self.assertIn("## 1. Text One", text)
        self.assertIn("- Domain: text", text)
        self.assertIn("- Price: 0", text)

    def test_format_records_as_json(self):
        text = format_records_as_json([record("Text One", "text", 1)])

        self.assertIn('"title": "Text One"', text)
        self.assertIn('"domain": "text"', text)
        self.assertIn('"price": 0.0', text)

    def test_format_records_as_csv(self):
        text = format_records_as_csv([record("Text One", "text", 1)])

        self.assertTrue(text.startswith("title,description,slug,url,type,domain,created,price\n"))
        self.assertIn("Text One", text)

    def test_write_export_counts_records_by_format(self):
        records = [record("Text One", "text", 2), record("Image One", "image", 1)]
        with TemporaryDirectory() as directory:
            output_dir = Path(directory)
            for export_format in ("txt", "markdown", "json", "csv"):
                output_path = write_export(output_dir, "acb", "all", records, export_format)
                self.assertEqual(count_written_records(output_path, export_format), 2)

    def test_sorted_newest_to_oldest(self):
        self.assertTrue(sorted_newest_to_oldest([record("A", "text", 2), record("B", "text", 1)]))
        self.assertFalse(sorted_newest_to_oldest([record("A", "text", 1), record("B", "text", 2)]))


if __name__ == "__main__":
    unittest.main()
