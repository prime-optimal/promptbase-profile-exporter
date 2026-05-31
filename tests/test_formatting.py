import unittest

from promptbase_exporter.formatting import (
    filter_records,
    format_records_as_text,
    sorted_newest_to_oldest,
)
from promptbase_exporter.models import PromptRecord


def record(title, domain, created):
    return PromptRecord(
        title=title,
        description=f"{title} description",
        slug=title.lower().replace(" ", "-"),
        prompt_type="gpt" if domain == "text" else "chatgpt-image",
        domain=domain,
        created=created,
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

    def test_format_records_as_text(self):
        text = format_records_as_text([record("Text One", "text", 1)])

        self.assertIn("1.\nTitle: Text One\nDescription:\nText One description", text)

    def test_sorted_newest_to_oldest(self):
        self.assertTrue(sorted_newest_to_oldest([record("A", "text", 2), record("B", "text", 1)]))
        self.assertFalse(sorted_newest_to_oldest([record("A", "text", 1), record("B", "text", 2)]))


if __name__ == "__main__":
    unittest.main()
