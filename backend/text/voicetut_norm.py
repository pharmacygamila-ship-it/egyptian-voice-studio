"""طبقة تطبيع مصري متقدّمة مبنية على حزمة `voicetut-tts` + قاموس المشروع.

لو الحزمة متثبّتة بنستخدمها (تطبيع أرقام/تواريخ/أوقات/عملات/ميل/اختصارات +
تشكيل + تحويل الأسماء الإنجليزية)، وإلا بنرجع للمطبّع المدمج في `normalize.py`.

ميزة إنها CPU-only (من غير torch) إنها تشتغل على أي جهاز، فالتحسين ده متاح
دلوقتي حتى قبل ما نشغّل الموديل على GPU.

    from backend.text.voicetut_norm import available, normalize
    if available():
        print(normalize("عرض 50% على قهوة بون النهاردة"))
"""
from __future__ import annotations

from typing import Dict, Optional

# كاش للمطبّعات حسب الإعدادات (التشكيل/الأرقام/الأسماء)
_CACHE: dict[tuple[bool, bool, bool], object] = {}


def available() -> bool:
    """هل حزمة voicetut-tts متثبّتة؟"""
    try:
        import voicetut_tts  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _get(diacritics: bool, numbers: bool, names: bool, keep_latin: bool):
    key = (diacritics, numbers, names, keep_latin)
    cached = _CACHE.get(key)
    if cached is None:
        from voicetut_tts import ArabicNormalizer, NormalizerConfig

        cfg = NormalizerConfig(
            apply_diacritics=diacritics,
            expand_numbers=numbers,
            transliterate_names=names,
            keep_latin=keep_latin,
        )
        cached = ArabicNormalizer(cfg)
        _CACHE[key] = cached
    return cached


def normalize(
    text: str,
    *,
    diacritics: bool = True,
    numbers: bool = True,
    names: bool = True,
    keep_latin: bool = True,
    lexicon: Optional[Dict[str, str]] = None,
) -> str:
    """تطبيع النص بطبقة VoiceTut.

    المعاملات:
        diacritics : يشكّل الكلمات (بيحسّن نطق الأرقام والمصطلحات).
        numbers    : يحوّل الأرقام لكلام مصري.
        names      : يحوّل أسماء إنجليزية معروفة لعربي (Ahmed → أحمد).
        keep_latin : يسيب الكلمات الإنجليزية زي ما هي (code-switching).
        lexicon    : تجاوزات إضافية project-specific: {"Ziad": "زياد"}.
    """
    if not text:
        return ""
    n = _get(diacritics, numbers, names, keep_latin)
    if lexicon:
        n.add_names(dict(lexicon))
    return n(text)
