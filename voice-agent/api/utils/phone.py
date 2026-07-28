"""
Phone number normalization utilities.

Provides a single canonical normalization function that is used everywhere
phone numbers need to be compared, stored or looked up.
"""

import re
from typing import List, Set


def normalize_phone_number(number: str) -> str:
    """
    Normalize a phone number to canonical E.164 format with a leading +.

    Supported input formats:
      +91xxxxxxxxxx
      91xxxxxxxxxx
      0xxxxxxxxxx
      xxxxxxxxxx
      +1 (555) 123-4567

    Returns:
        E.164 string like '+919876543210' or '+15550123'.
        Returns empty string if no digits are found.
    """
    if not number:
        return ""

    raw = str(number).strip()
    digits = re.sub(r"\D", "", raw)

    if not digits:
        return ""

    # Remove a single leading zero (local trunk prefix) if present
    if digits.startswith("0") and len(digits) > 1:
        digits = digits[1:]

    return f"+{digits}"


def get_phone_number_variants(number: str) -> List[str]:
    """
    Return a list of possible representations for a phone number.

    This makes lookups robust to carriers that send numbers with or without
    a leading + or country code.

    Examples:
      +919876543210 -> ["+919876543210", "919876543210", "9876543210"]
      +15550123     -> ["+15550123", "15550123", "5550123"]
    """
    e164 = normalize_phone_number(number)
    if not e164:
        return []

    digits = e164[1:]  # strip leading +
    variants: Set[str] = {e164, digits}

    # Local number: last 10 digits (covers NANP 10-digit and most global mobile)
    if len(digits) >= 10:
        variants.add(digits[-10:])

    return list(variants)
