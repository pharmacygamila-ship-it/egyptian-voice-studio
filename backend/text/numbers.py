"""تحويل الأرقام لكلام بالصيغة المصرية (مش الفصحى).

أمثلة:
    50      → خمسين
    2026    → ألفين وستة وعشرين
    1500    → ألف وخمسمية
    3.5     → تلاتة فاصلة خمسة
    3:30    → تلاتة وتلاتين
    010012... → صفر واحد صفر ...  (رقم رقم)

الموديلات بتغلط في نطق الأرقام بالعامية، فالطبقة دي بتحوّلها كلام قبل التوليد.
"""
from __future__ import annotations

import re

_ONES = ["صفر", "واحد", "اتنين", "تلاتة", "أربعة", "خمسة", "ستة", "سبعة", "تمانية", "تسعة"]

_TEENS = {
    10: "عشرة", 11: "حداشر", 12: "اتناشر", 13: "تلتاشر", 14: "أربعتاشر",
    15: "خمستاشر", 16: "ستاشر", 17: "سبعتاشر", 18: "تمانتاشر", 19: "تسعتاشر",
}

_TENS = {
    20: "عشرين", 30: "تلاتين", 40: "أربعين", 50: "خمسين",
    60: "ستين", 70: "سبعين", 80: "تمانين", 90: "تسعين",
}

_HUNDREDS = {
    100: "مية", 200: "ميتين", 300: "تلتمية", 400: "أربعمية", 500: "خمسمية",
    600: "ستمية", 700: "سبعمية", 800: "تمنمية", 900: "تسعمية",
}


def _below_1000(n: int) -> str:
    parts: list[str] = []
    if n >= 100:
        parts.append(_HUNDREDS[(n // 100) * 100])
        n %= 100
    if n:
        if n < 10:
            parts.append(_ONES[n])
        elif n < 20:
            parts.append(_TEENS[n])
        else:
            tens, unit = (n // 10) * 10, n % 10
            parts.append(f"{_ONES[unit]} و{_TENS[tens]}" if unit else _TENS[tens])
    return " و".join(parts)


def _scale(k: int, singular: str, dual: str, plural: str) -> str:
    if k == 1:
        return singular
    if k == 2:
        return dual
    if 3 <= k <= 10:
        return f"{_below_1000(k)} {plural}"
    return f"{_below_1000(k)} {singular}"


def int_to_words(n: int) -> str:
    """يحوّل عدد صحيح لكلام مصري (0 → تريليون تقريباً)."""
    if n < 0:
        return "سالب " + int_to_words(-n)
    if n == 0:
        return _ONES[0]

    parts: list[str] = []

    millions = n // 1_000_000
    n %= 1_000_000
    thousands = n // 1000
    n %= 1000

    billions = millions // 1000
    millions %= 1000

    if billions:
        parts.append(_scale(billions, "مليار", "مليارين", "مليار"))
    if millions:
        parts.append(_scale(millions, "مليون", "مليونين", "ملايين"))
    if thousands:
        parts.append(_scale(thousands, "ألف", "ألفين", "آلاف"))
    if n:
        parts.append(_below_1000(n))

    return " و".join(p for p in parts if p)


def digits_to_words(digits: str) -> str:
    """يقرأ رقم رقم (زي أرقام التليفون)."""
    return " ".join(_ONES[int(d)] for d in digits if d.isdigit())


# ── التوسيع داخل النص ────────────────────────────────────────────────────
_THOUSANDS_COMMA = re.compile(r"(?<=\d)[,،](?=\d{3}\b)")
_TIME = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
_LONG_DIGITS = re.compile(r"(?<!\d)\d{8,}(?!\d)")
_DECIMAL = re.compile(r"(?<!\d)(\d+)\.(\d+)(?!\d)")
_INTEGER = re.compile(r"(?<!\d)(\d+)(?!\d)")


def expand_numbers(text: str) -> str:
    """يحوّل كل الأرقام في النص لكلام مصري."""
    if not text:
        return text

    text = _THOUSANDS_COMMA.sub("", text)
    text = _TIME.sub(
        lambda m: f"{int_to_words(int(m.group(1)))} و{int_to_words(int(m.group(2)))}", text
    )
    text = _LONG_DIGITS.sub(lambda m: digits_to_words(m.group(0)), text)
    text = _DECIMAL.sub(
        lambda m: (
            f"{int_to_words(int(m.group(1)))} فاصلة "
            f"{int_to_words(int(m.group(2).rstrip('0') or '0'))}"
        ),
        text,
    )
    text = _INTEGER.sub(lambda m: int_to_words(int(m.group(1))), text)
    return text
