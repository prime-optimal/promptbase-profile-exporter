import unittest

from promptbase_exporter.client import parse_profile_input


class ParseProfileInputTests(unittest.TestCase):
    def test_full_url(self):
        self.assertEqual(
            parse_profile_input("https://promptbase.com/profile/acb"),
            "acb",
        )

    def test_profile_path(self):
        self.assertEqual(parse_profile_input("profile/acb"), "acb")

    def test_username(self):
        self.assertEqual(parse_profile_input("acb"), "acb")

    def test_at_username(self):
        self.assertEqual(parse_profile_input("@acb"), "acb")


if __name__ == "__main__":
    unittest.main()
