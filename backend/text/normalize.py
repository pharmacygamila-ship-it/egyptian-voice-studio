"""تطبيع النص المصري قبل ما يروح للمحرك.

الموديل عنده تطبيع داخلي (خانة Normalize)، بس الطبقة دي بتضيف حاجات
مخصوصة للعامية المصرية والإعلانات:

- تفكيك الاختصارات والرموز
- الأرقام بالكلام المصري (خمسين مش 50)
- النطق المصري للكلمات الأجنبية (واتساب مش WhatsApp)
- تنضيف الإيموجي والتطويل والحروف المكرّرة

كل حاجة قابلة للتعديل/الإطفاء من خلال الـ parameters.
"""
from __future__ import annotations

import re

from . import numbers as _numbers
from . import voicetut_norm as _vt_norm
from .diacritics import apply_diacritics
from .lexicon import apply_lexicon, expand_units

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

# إيموجي ورموز زخرفية
_EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0000fe00-\U0000fe0f"
    "\U00002b00-\U00002bff\U0001f1e6-\U0001f1ff\u200d\u2060\ufeff]"
)

# تطويل الحروف العربية (حلوووو → حلو)
_ELONGATION = re.compile(r"([\u0621-\u064A])\1{2,}")

# حروف تعتبر "جزء من كلمة" (عربي + لاتيني + أرقام)
_WORDCHARS = r"0-9A-Za-z_\u0600-\u06FF"


def _replace_standalone(text: str, token: str, repl: str) -> str:
    """يستبدل الرمز/الاختصار لما يكون كلمة مستقلة بس (مش جوه كلمة)."""
    pattern = rf"(?<![{_WORDCHARS}]){re.escape(token)}(?![{_WORDCHARS}])"
    return re.sub(pattern, repl, text)


def normalize_egyptian(
    text: str,
    *,
    fold_digits: bool = True,
    numbers: bool = True,
    use_lexicon: bool = True,
    diacritics: bool = False,
    clean: bool = True,
) -> str:
    """تطبيع النص المصري.

    المعاملات:
        fold_digits : يحوّل الأرقام الشرقية (٥) لغربية (5)
        numbers     : يحوّل الأرقام لكلام مصري (50 → خمسين)
        use_lexicon : يستبدل الكلمات الأجنبية بنطق مصري (واتساب)
        diacritics  : يشكّل كلمات إعلانية ملتبسة (اختياري — راجع diacritics.py)
        clean       : يشيل الإيموجي والتطويل والحروف المكرّرة
    """
    if not text:
        return ""

    out = text.strip()

    # تطويل صريح (ـ)
    out = out.replace("\u0640", "")

    if fold_digits:
        out = out.translate(_AR_DIGITS)

    if clean:
        out = _EMOJI.sub("", out)
        out = _ELONGATION.sub(r"\1", out)

    # النسب المئوية: "50٪" / "50 %" → "50 في المية"
    out = re.sub(r"(\d+)\s*[٪%]", r"\1 في المية", out)
    out = re.sub(r"[٪%]", " في المية ", out)

    for sym, repl in _SYMBOLS.items():
        out = out.replace(sym, repl)

    # اختصارات (الأطول الأول عشان التداخل) — كلمات مستقلة بس
    for abbr in sorted(_ABBREVIATIONS, key=len, reverse=True):
        out = _replace_standalone(out, abbr, _ABBREVIATIONS[abbr])

    if use_lexicon:
        out = apply_lexicon(out)

    if diacritics:
        out = apply_diacritics(out)

    # وحدات ملزوقة بالأرقام: 5kg → 5 كيلوجرام (قبل توسيع الأرقام)
    out = expand_units(out)

    if numbers:
        out = _numbers.expand_numbers(out)

    # توحيد المسافات والفواصل
    out = _WHITESPACE.sub(" ", out)
    out = re.sub(r"\s+([،؛:.!?])", r"\1", out)
    out = re.sub(r"[!?]{2,}", "!", out)
    out = _MULTI_NEWLINE.sub("\n", out)

    return out.strip()


def normalize_for_tts(
    text: str,
    *,
    diacritics: bool = True,
    numbers: bool = True,
    names: bool = True,
    lexicon: dict[str, str] | None = None,
    clean: bool = True,
    modern: bool | None = None,
) -> str:
    """التطبيع النهائي قبل ما النص يروح للمحرك.

    لو حزمة `voicetut-tts` متثبّتة بنستخدم طبقتها المتقدّمة (تطبيع أرقام/تواريخ/
    أوقات + تشكيل + أسماء)، وهي نفس الطبقة اللي الموديل اتدرّب عليها — وده أضمن
    للنطق. ولو مش متثبّتة بنرجع للمطبّع المدمج.

    المعاملات:
        diacritics : يشكّل الكلمات (الافتراضي مفعّل في الطبقة الجديدة).
        numbers    : يحوّل الأرقام لكلام مصري.
        names      : يحوّل الأسماء الإنجليزية المعروفة لعربي.
        lexicon    : تجاوزات إضافية {"Ziad": "زياد"}.
        clean      : يشيل الإيموجي/التطويل/الحروف المكرّرة.
        modern     : None = تلقائي (لو الحزمة متاحة)، True/False للإجبار.
    """
    if not text:
        return ""

    if modern is None:
        modern = _vt_norm.available()

    if modern:
        out = text
        if clean:
            out = out.replace("\u0640", "")
            out = _EMOJI.sub("", out)
            out = _ELONGATION.sub(r"\1", out)
        out = _vt_norm.normalize(
            out,
            diacritics=diacritics,
            numbers=numbers,
            names=names,
            lexicon=lexicon,
        )
        out = _WHITESPACE.sub(" ", out)
        return out.strip()

    return normalize_egyptian(
        text,
        numbers=numbers,
        diacritics=diacritics,
        clean=clean,
    )


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
