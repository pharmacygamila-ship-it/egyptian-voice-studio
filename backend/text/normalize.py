"""تطبيع النص المصري قبل ما يروح للمحرك.

الموديل عنده تطبيع داخلي (خانة Normalize)، بس الطبقة دي بتضيف حاجات
مخصوصة للعامية المصرية والإعلانات، وبتنضّف النص قبل التوليد.

قابل للتوسيع — دي بداية عملية مش نهائية.
"""
from __future__ import annotations

import re

# أرقام عربية شرقية → غربية
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# اختصارات شائعة في الإعلانات تتفكّك عشان النطق يبقى صح
_ABBREVIATIONS: dict[str, str] = {
    "ب.م": "بعد الميلاد",
    "ق.م": "قبل الميلاد",
    "ج.م": "جنيه مصري",
    "ر.س": "ريال سعودي",
    "د.إ": "درهم إماراتي",
    "ت": "تليفون",
    "م": "متر",
    "كم": "كيلومتر",
    "كجم": "كيلوجرام",
    "&": "و",
    "+": "زائد",
}

# رموز بتتقرأ كلمة
_SYMBOLS: dict[str, str] = {
    "@": " at ",
    "#": " هاشتاج ",
    "*": " ",
    "–": "-",
    "—": "-",
    "…": ".",
    "“": '"',
    "”": '"',
    "„": '"',
}

_WHITESPACE = re.compile(r"[ \t\u00a0]+")
_MULTI_NEWLINE = re.compile(r"\n{2,}")

# حروف تعتبر "جزء من كلمة" (عربي + لاتيني + أرقام)
_WORDCHARS = r"0-9A-Za-z_\u0600-\u06FF"


def _replace_standalone(text: str, token: str, repl: str) -> str:
    """يستبدل الرمز/الاختصار لما يكون كلمة مستقلة بس (مش جوه كلمة)."""
    pattern = rf"(?<![{_WORDCHARS}]){re.escape(token)}(?![{_WORDCHARS}])"
    return re.sub(pattern, repl, text)


def normalize_egyptian(text: str, *, fold_digits: bool = True) -> str:
    """تطبيع أساسي للنص المصري.

    - يوحّد الأرقام والمسافات
    - يفكّ الاختصارات والرموز
    - يشيل التشكيل الزائد والتطويل
    - يحافظ على الكلمات الإنجليزية كما هي (code-switching)
    """
    if not text:
        return ""

    out = text.strip()

    # تطويل
    out = out.replace("\u0640", "")

    if fold_digits:
        out = out.translate(_AR_DIGITS)

    # النسب المئوية: "50٪" / "50 %" → "50 في المية"
    out = re.sub(r"(\d+)\s*[٪%]", r"\1 في المية", out)
    out = re.sub(r"[٪%]", " في المية ", out)

    for sym, repl in _SYMBOLS.items():
        out = out.replace(sym, repl)

    # اختصارات (الأطول الأول عشان التداخل) — كلمات مستقلة بس
    for abbr in sorted(_ABBREVIATIONS, key=len, reverse=True):
        out = _replace_standalone(out, abbr, _ABBREVIATIONS[abbr])

    # توحيد المسافات والفواصل
    out = _WHITESPACE.sub(" ", out)
    out = re.sub(r"\s+([،؛:.!?])", r"\1", out)
    out = _MULTI_NEWLINE.sub("\n", out)

    return out.strip()


def split_sentences(text: str, max_chars: int = 300) -> list[str]:
    """يقطّع النص لجُمل مناسبة للبث/التوليد الطويل."""
    parts = re.split(r"(?<=[.!?؟،])\s+", text.strip())
    chunks: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if chunks and len(chunks[-1]) + len(part) + 1 <= max_chars:
            chunks[-1] = f"{chunks[-1]} {part}"
        else:
            chunks.append(part)
    return chunks or ([text.strip()] if text.strip() else [])
