"""
Phone number normalization for customer search (research R1).

Numbers are stored as staff typed them; a digits-only form is kept
alongside for matching, so "+63 917 123 4567", "0917-123-4567" and
"(0917) 1234567" all compare equal.
"""

import re

PHONE_CHARACTERS = re.compile(r"^[\d\s+\-()]+$")
_NON_DIGITS = re.compile(r"\D")


def normalize_phone(value):
    """
    Returns the digits of ``value``, with the Philippine country code ``63``
    replaced by a leading ``0`` when the number is complete (12 digits) or
    the text explicitly starts with ``+63``. Returns "" for empty input.
    """
    if not value:
        return ""

    text = str(value).strip()
    digits = _NON_DIGITS.sub("", text)

    if digits.startswith("63") and (len(digits) == 12 or text.startswith("+63")):
        digits = "0" + digits[2:]

    return digits


def is_phone_query(value):
    """True when ``value`` contains only phone characters and at least one digit."""
    if not value:
        return False

    text = value.strip()
    return bool(PHONE_CHARACTERS.match(text)) and any(c.isdigit() for c in text)
