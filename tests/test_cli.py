import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from promptbase_exporter.cli import count_by, main, parse_datetime_ms
from promptbase_exporter.models import Profile, PromptRecord


def record(title, domain, prompt_type, price=0.0, created=1):
    return PromptRecord(
        title=title,
        description=f"{title} description",
        slug=title.lower().replace(" ", "-"),
        prompt_type=prompt_type,
        domain=domain,
        created=created,
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
        self.assertIn("Planned outputs:", stdout.getvalue())
        self.assertIn("all: 1", stdout.getvalue())
        self.assertIn("text: 1", stdout.getvalue())
        self.assertIn("image: 0", stdout.getvalue())
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

    def test_output_file_refuses_existing_without_overwrite(self):
        records = [record("A", "text", "gpt")]
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "catalog.json"
            output_path.write_text("[]\n", encoding="utf-8")
            with patch(
                "promptbase_exporter.cli.fetch_prompts",
                return_value=(Profile(username="acb", uid="uid-1"), records),
            ):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = main(["@acb", "--mode", "all", "--output-file", str(output_path)])

        self.assertEqual(exit_code, 1)

    def test_output_file_infers_json_and_writes(self):
        records = [record("A", "text", "gpt")]
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "catalog.json"
            with patch(
                "promptbase_exporter.cli.fetch_prompts",
                return_value=(Profile(username="acb", uid="uid-1"), records),
            ):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = main(["@acb", "--mode", "all", "--output-file", str(output_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn('"title": "A"', output_path.read_text(encoding="utf-8"))

    def test_update_file_compares_and_rewrites_existing_catalog(self):
        records = [record("New", "text", "gpt")]
        old_text = "1.\nTitle: Old\nDescription:\nOld description\n"
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "catalog.txt"
            output_path.write_text(old_text, encoding="utf-8")
            stdout = io.StringIO()
            with patch(
                "promptbase_exporter.cli.fetch_prompts",
                return_value=(Profile(username="acb", uid="uid-1"), records),
            ), redirect_stdout(stdout):
                exit_code = main(["@acb", "--mode", "all", "--update-file", str(output_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn("- Added: 1", stdout.getvalue())
            self.assertIn("Title: New", output_path.read_text(encoding="utf-8"))

    def test_compare_can_fail_on_diff(self):
        records = [record("New", "text", "gpt")]
        with TemporaryDirectory() as directory:
            previous_path = Path(directory) / "catalog.json"
            previous_path.write_text("[]\n", encoding="utf-8")
            stdout = io.StringIO()
            with patch(
                "promptbase_exporter.cli.fetch_prompts",
                return_value=(Profile(username="acb", uid="uid-1"), records),
            ), redirect_stdout(stdout):
                exit_code = main(
                    [
                        "@acb",
                        "--mode",
                        "all",
                        "--compare",
                        str(previous_path),
                        "--fail-on-diff",
                    ]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("- Added: 1", stdout.getvalue())

    def test_update_file_rewrites_even_when_fail_on_diff_returns_two(self):
        records = [record("New", "text", "gpt")]
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "catalog.txt"
            output_path.write_text("", encoding="utf-8")
            stdout = io.StringIO()
            with patch(
                "promptbase_exporter.cli.fetch_prompts",
                return_value=(Profile(username="acb", uid="uid-1"), records),
            ), redirect_stdout(stdout):
                exit_code = main(
                    [
                        "@acb",
                        "--mode",
                        "all",
                        "--update-file",
                        str(output_path),
                        "--fail-on-diff",
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("- Added: 1", stdout.getvalue())
            self.assertIn("Title: New", output_path.read_text(encoding="utf-8"))

    def test_since_until_and_limit_filter_selected_records(self):
        records = [
            record(
                "Newest",
                "text",
                "gpt",
                created=parse_datetime_ms("2026-03-01", end_of_day=False),
            ),
            record(
                "Middle",
                "text",
                "gpt",
                created=parse_datetime_ms("2026-02-01", end_of_day=False),
            ),
            record(
                "Oldest",
                "text",
                "gpt",
                created=parse_datetime_ms("2026-01-01", end_of_day=False),
            ),
        ]
        with patch(
            "promptbase_exporter.cli.fetch_prompts",
            return_value=(Profile(username="acb", uid="uid-1"), records),
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "@acb",
                        "--since",
                        "2026-01-15",
                        "--until",
                        "2026-03-31",
                        "--limit",
                        "1",
                        "--dry-run",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("Selected after filters: 1", stdout.getvalue())

    def test_text_only_mode_alias_writes_text_export(self):
        records = [
            record("A", "text", "gpt"),
            record("B", "image", "chatgpt-image"),
        ]
        with patch(
            "promptbase_exporter.cli.fetch_prompts",
            return_value=(Profile(username="acb", uid="uid-1"), records),
        ), patch("promptbase_exporter.cli.write_export") as write_export, patch(
            "promptbase_exporter.cli.count_written_records",
            return_value=1,
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["@acb", "--mode", "text-only"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(write_export.call_args.args[2], "text")
        self.assertEqual([record.title for record in write_export.call_args.args[3]], ["A"])

    def test_image_only_mode_alias_writes_image_export(self):
        records = [
            record("A", "text", "gpt"),
            record("B", "image", "chatgpt-image"),
        ]
        with patch(
            "promptbase_exporter.cli.fetch_prompts",
            return_value=(Profile(username="acb", uid="uid-1"), records),
        ), patch("promptbase_exporter.cli.write_export") as write_export, patch(
            "promptbase_exporter.cli.count_written_records",
            return_value=1,
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["@acb", "--mode", "image-only"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(write_export.call_args.args[2], "image")
        self.assertEqual([record.title for record in write_export.call_args.args[3]], ["B"])

    def test_version_argument_exits(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
            main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("promptbase-export", stdout.getvalue())


class ArgumentValidationTests(unittest.TestCase):
    """Invalid arguments must fail before any network fetch."""

    def _run_expecting_failure(self, argv):
        with patch("promptbase_exporter.cli.fetch_prompts") as fetch:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = main(argv)
        fetch.assert_not_called()
        return exit_code, stderr.getvalue()

    def test_negative_min_price_fails_before_fetch(self):
        exit_code, stderr = self._run_expecting_failure(["@acb", "--min-price", "-1"])
        self.assertEqual(exit_code, 1)
        self.assertIn("--min-price cannot be negative", stderr)

    def test_negative_max_price_fails_before_fetch(self):
        exit_code, stderr = self._run_expecting_failure(["@acb", "--max-price", "-2"])
        self.assertEqual(exit_code, 1)
        self.assertIn("--max-price cannot be negative", stderr)

    def test_min_price_greater_than_max_fails_before_fetch(self):
        exit_code, stderr = self._run_expecting_failure(
            ["@acb", "--min-price", "5", "--max-price", "1"]
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("--min-price cannot be greater than --max-price", stderr)

    def test_non_positive_limit_fails_before_fetch(self):
        exit_code, stderr = self._run_expecting_failure(["@acb", "--limit", "0"])
        self.assertEqual(exit_code, 1)
        self.assertIn("--limit must be greater than zero", stderr)


class ParseDatetimeTests(unittest.TestCase):
    def test_empty_value_raises(self):
        with self.assertRaises(ValueError):
            parse_datetime_ms("   ", end_of_day=False)

    def test_invalid_value_raises_with_guidance(self):
        for value in ("not-a-date", "2026-13-01", "2026-02-30"):
            with self.assertRaises(ValueError) as raised:
                parse_datetime_ms(value, end_of_day=False)
            self.assertIn("YYYY-MM-DD", str(raised.exception))

    def test_date_only_start_and_end_of_day_bracket_the_day(self):
        start = parse_datetime_ms("2026-01-01", end_of_day=False)
        end = parse_datetime_ms("2026-01-01", end_of_day=True)
        self.assertLess(start, end)
        # The bracket stays within a single 24h window.
        self.assertLess(end - start, 24 * 60 * 60 * 1000)

    def test_date_only_is_interpreted_as_utc_midnight(self):
        self.assertEqual(
            parse_datetime_ms("2026-01-01", end_of_day=False),
            parse_datetime_ms("2026-01-01T00:00:00+00:00", end_of_day=False),
        )

    def test_naive_datetime_is_assumed_utc(self):
        self.assertEqual(
            parse_datetime_ms("2026-01-01T12:00:00", end_of_day=False),
            parse_datetime_ms("2026-01-01T12:00:00Z", end_of_day=False),
        )

    def test_timezone_aware_datetime_is_converted_to_utc(self):
        # 00:00 at +01:00 is the previous day at 23:00 UTC.
        self.assertEqual(
            parse_datetime_ms("2026-01-01T00:00:00+01:00", end_of_day=False),
            parse_datetime_ms("2025-12-31T23:00:00+00:00", end_of_day=False),
        )


if __name__ == "__main__":
    unittest.main()
