import unittest
from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory

from promptbase_exporter.models import Profile, PromptRecord
from promptbase_exporter.web import (
    ExportRequest,
    PromptBaseWebHandler,
    WebInputError,
    build_request_config,
    render_form,
    run_export,
)


class _FakeServer:
    def __init__(self, address):
        self.server_address = address


def _make_handler(headers, address=("127.0.0.1", 8765)):
    handler = PromptBaseWebHandler.__new__(PromptBaseWebHandler)
    message = Message()
    for key, value in headers.items():
        message[key] = value
    handler.headers = message
    handler.server = _FakeServer(address)
    return handler


def record(title, domain, prompt_type, created=1, price=0.0, description=None):
    return PromptRecord(
        title=title,
        description=f"{title} description" if description is None else description,
        slug=title.lower().replace(" ", "-"),
        prompt_type=prompt_type,
        domain=domain,
        created=created,
        price=price,
    )


class WebTests(unittest.TestCase):
    def test_build_request_config_normalizes_form_values(self):
        config = build_request_config(
            {
                "profile": ["https://promptbase.com/profile/acb"],
                "mode": ["text"],
                "format": ["json"],
                "sort": ["views"],
                "domain": [" text "],
                "prompt_type": ["gpt"],
                "price_filter": ["paid"],
                "min_price": ["1.5"],
                "max_price": ["5"],
                "limit": ["10"],
                "since": ["2026-01-01"],
                "until": ["2026-12-31"],
                "timestamp_filenames": ["1"],
                "allow_missing_descriptions": ["on"],
                "output_dir": ["exports/acb"],
            }
        )

        self.assertEqual(config.profile_input, "https://promptbase.com/profile/acb")
        self.assertEqual(config.mode, "text")
        self.assertEqual(config.export_format, "json")
        self.assertEqual(config.sort, "views")
        self.assertEqual(config.domain, "text")
        self.assertEqual(config.prompt_type, "gpt")
        self.assertEqual(config.price_filter, "paid")
        self.assertEqual(config.min_price, 1.5)
        self.assertEqual(config.max_price, 5.0)
        self.assertEqual(config.limit, 10)
        self.assertEqual(config.since, "2026-01-01")
        self.assertEqual(config.until, "2026-12-31")
        self.assertTrue(config.timestamp_filenames)
        self.assertTrue(config.allow_missing_descriptions)
        self.assertIsInstance(config.output_dir, Path)
        self.assertTrue(config.output_dir.is_absolute())
        self.assertTrue(config.output_dir.is_relative_to(Path.cwd().resolve()))

    def test_build_request_config_rejects_output_dir_escape(self):
        for escape in ("..", "../outside", "../../etc", "exports/../../secrets"):
            with self.assertRaises(WebInputError):
                build_request_config({"profile": "acb", "output_dir": escape})

    def test_build_request_config_rejects_absolute_output_dir(self):
        absolute = "C:\\Windows\\Temp" if Path("C:\\").exists() else "/etc"
        with self.assertRaises(WebInputError):
            build_request_config({"profile": "acb", "output_dir": absolute})

    def test_build_request_config_rejects_invalid_prices(self):
        with self.assertRaises(WebInputError):
            build_request_config(
                {
                    "profile": "acb",
                    "min_price": "10",
                    "max_price": "5",
                }
            )

    def test_build_request_config_rejects_invalid_dates(self):
        for field in ("since", "until"):
            with self.assertRaises(WebInputError):
                build_request_config({"profile": "acb", field: "not-a-date"})

    def test_render_form_contains_expected_controls(self):
        html = render_form(ExportRequest(profile_input="@acb"))

        self.assertIn("PromptBase Profile Exporter", html)
        self.assertIn('name="profile"', html)
        self.assertIn('name="mode"', html)
        self.assertIn('value="@acb"', html)
        self.assertIn('value="split" selected', html)
        self.assertIn('name="price_filter"', html)
        self.assertIn('name="since"', html)
        self.assertIn('name="limit"', html)

    def test_run_export_writes_split_outputs(self):
        records = [
            record("Text One", "text", "gpt", created=3),
            record("Image One", "image", "chatgpt-image", created=2),
        ]

        def fetcher(profile_input):
            self.assertEqual(profile_input, "@acb")
            return Profile(username="acb", uid="uid-1"), records

        with TemporaryDirectory() as directory:
            request = ExportRequest(
                profile_input="@acb",
                output_dir=Path(directory),
                mode="split",
                export_format="csv",
            )

            result = run_export(request, fetcher=fetcher)

            self.assertEqual(result.username, "acb")
            self.assertEqual(result.total_records, 2)
            self.assertEqual(result.selected_records, 2)
            self.assertEqual([item.mode for item in result.files], ["all", "text", "image"])
            self.assertEqual([item.count for item in result.files], [2, 1, 1])
            for item in result.files:
                self.assertTrue(item.path.exists())

    def test_run_export_applies_filters_and_sorting(self):
        records = [
            record("Cheap", "text", "gpt", created=3, price=1.0),
            record("Expensive", "text", "gpt", created=2, price=9.0),
            record("Image", "image", "chatgpt-image", created=1, price=4.0),
        ]

        def fetcher(_profile_input):
            return Profile(username="acb", uid="uid-1"), records

        with TemporaryDirectory() as directory:
            request = ExportRequest(
                profile_input="@acb",
                output_dir=Path(directory),
                mode="text",
                export_format="txt",
                domain="text",
                price_filter="paid",
                min_price=5.0,
                limit=1,
                sort="price",
            )

            result = run_export(request, fetcher=fetcher)

            self.assertEqual(result.selected_records, 1)
            self.assertEqual(result.files[0].count, 1)
            self.assertIn("Expensive", result.files[0].path.read_text(encoding="utf-8"))

    def test_run_export_requires_descriptions_by_default(self):
        def fetcher(_profile_input):
            return Profile(username="acb", uid="uid-1"), [
                record("Missing", "text", "gpt", description="")
            ]

        with TemporaryDirectory() as directory:
            request = ExportRequest(profile_input="@acb", output_dir=Path(directory))

            with self.assertRaises(WebInputError):
                run_export(request, fetcher=fetcher)


class RequestGuardTests(unittest.TestCase):
    def test_allows_same_origin_sec_fetch_site(self):
        handler = _make_handler(
            {"Host": "127.0.0.1:8765", "Sec-Fetch-Site": "same-origin"}
        )
        self.assertIsNone(handler._reject_unsafe_request())

    def test_allows_none_sec_fetch_site(self):
        handler = _make_handler({"Host": "localhost:8765", "Sec-Fetch-Site": "none"})
        self.assertIsNone(handler._reject_unsafe_request())

    def test_rejects_cross_site_sec_fetch_site(self):
        handler = _make_handler(
            {"Host": "127.0.0.1:8765", "Sec-Fetch-Site": "cross-site"}
        )
        self.assertIsNotNone(handler._reject_unsafe_request())

    def test_rejects_foreign_origin(self):
        handler = _make_handler(
            {"Host": "127.0.0.1:8765", "Origin": "http://evil.example"}
        )
        self.assertIsNotNone(handler._reject_unsafe_request())

    def test_allows_matching_origin(self):
        handler = _make_handler(
            {"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"}
        )
        self.assertIsNone(handler._reject_unsafe_request())

    def test_rejects_rebound_host_header(self):
        handler = _make_handler({"Host": "attacker.example:8765"})
        self.assertIsNotNone(handler._reject_unsafe_request())

    def test_allows_non_browser_client_without_headers(self):
        handler = _make_handler({"Host": "127.0.0.1:8765"})
        self.assertIsNone(handler._reject_unsafe_request())


if __name__ == "__main__":
    unittest.main()
