from django.test import SimpleTestCase

from customers.phone import is_phone_query, normalize_phone


class NormalizePhoneTests(SimpleTestCase):
    def test_normalizes_formats(self):
        cases = {
            "+63 917 123 4567": "09171234567",
            "0917-123-4567": "09171234567",
            "(0917) 1234567": "09171234567",
            "639171234567": "09171234567",
            "(02) 8123 4567": "0281234567",
            "  0917 123 4567  ": "09171234567",
            "": "",
            None: "",
            "n/a": "",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), expected)

    def test_partial_country_code(self):
        # "+63" is explicit, so the country code is converted at any length.
        self.assertEqual(normalize_phone("+63 917"), "0917")
        # A bare "63..." fragment could come from the middle of a number.
        self.assertEqual(normalize_phone("63917"), "63917")


class IsPhoneQueryTests(SimpleTestCase):
    def test_phone_like_queries(self):
        for query in ("4567", "+63 917", "0917-123", "(02) 8123", " 0917 "):
            with self.subTest(query=query):
                self.assertTrue(is_phone_query(query))

    def test_non_phone_queries(self):
        for query in ("ana", "ana 4567", "", "   ", "+-()"):
            with self.subTest(query=query):
                self.assertFalse(is_phone_query(query))
