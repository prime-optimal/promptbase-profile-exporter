import unittest

from promptbase_exporter.dates import parse_datetime_ms, re_full_date


class FullDateTests(unittest.TestCase):
    def test_recognizes_iso_date(self):
        self.assertTrue(re_full_date("2026-01-01"))

    def test_rejects_non_dates(self):
        for value in ("2026-1-1", "2026/01/01", "2026-01-01T00:00", "", "2026-01"):
            self.assertFalse(re_full_date(value))


class ParseDatetimeMsTests(unittest.TestCase):
    def test_bare_date_uses_utc_start_of_day(self):
        self.assertEqual(
            parse_datetime_ms("2026-01-01", end_of_day=False),
            1767225600000,
        )

    def test_bare_date_end_of_day_is_later_than_start(self):
        start = parse_datetime_ms("2026-01-01", end_of_day=False)
        end = parse_datetime_ms("2026-01-01", end_of_day=True)
        self.assertGreater(end, start)
        # End of day stays within the same calendar date.
        self.assertLess(end - start, 24 * 60 * 60 * 1000)

    def test_naive_datetime_assumed_utc(self):
        self.assertEqual(
            parse_datetime_ms("2026-01-01T00:00:00", end_of_day=False),
            parse_datetime_ms("2026-01-01", end_of_day=False),
        )

    def test_trailing_z_is_utc(self):
        self.assertEqual(
            parse_datetime_ms("2026-01-01T12:00:00Z", end_of_day=False),
            parse_datetime_ms("2026-01-01T12:00:00", end_of_day=False),
        )

    def test_offset_is_converted_to_utc(self):
        self.assertEqual(
            parse_datetime_ms("2026-01-01T01:00:00+01:00", end_of_day=False),
            parse_datetime_ms("2026-01-01T00:00:00+00:00", end_of_day=False),
        )

    def test_empty_value_rejected(self):
        with self.assertRaises(ValueError):
            parse_datetime_ms("   ", end_of_day=False)

    def test_invalid_value_rejected(self):
        for value in ("not-a-date", "2026-13-01", "2026-01-99"):
            with self.assertRaises(ValueError):
                parse_datetime_ms(value, end_of_day=False)


if __name__ == "__main__":
    unittest.main()
