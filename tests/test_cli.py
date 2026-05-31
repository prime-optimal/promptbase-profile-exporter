import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from promptbase_exporter.cli import count_by, main
from promptbase_exporter.models import Profile, PromptRecord


def record(title, domain, prompt_type, price=0.0):
    return PromptRecord(
        title=title,
        description=f"{title} description",
        slug=title.lower().replace(" ", "-"),
        prompt_type=prompt_type,
        domain=domain,
        created=1,
        price=price,
    )


class CliTests(unittest.TestCase):
    def test_count_by(self):
        records = [
            record("A", "text", "gpt"),
            record("B", "text", "claude"),
            record("C", "image", "chatgpt-image"),
        ]

        self.assertEqual(count_by(records, "domain"), {"text": 2, "image": 1})

    def test_dry_run_does_not_write_files(self):
        records = [record("A", "text", "gpt")]
        with patch(
            "promptbase_exporter.cli.fetch_prompts",
            return_value=(Profile(username="acb", uid="uid-1"), records),
        ), patch("promptbase_exporter.cli.write_export") as write_export:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["@acb", "--dry-run"])

        self.assertEqual(exit_code, 0)
        write_export.assert_not_called()
        self.assertIn("Dry run: no files written.", stdout.getvalue())

    def test_list_domains_exits_without_writing(self):
        records = [
            record("A", "text", "gpt"),
            record("B", "image", "chatgpt-image"),
        ]
        with patch(
            "promptbase_exporter.cli.fetch_prompts",
            return_value=(Profile(username="acb", uid="uid-1"), records),
        ), patch("promptbase_exporter.cli.write_export") as write_export:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["@acb", "--list-domains"])

        self.assertEqual(exit_code, 0)
        write_export.assert_not_called()
        self.assertIn("Domains:", stdout.getvalue())
        self.assertIn("text: 1", stdout.getvalue())

    def test_version_argument_exits(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
            main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("promptbase-export", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
