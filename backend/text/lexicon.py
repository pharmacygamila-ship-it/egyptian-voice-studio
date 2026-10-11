"""قاموس النطق + الاختصارات + الوحدات.

الهدف: الكلمات الأجنبية/الشائعة في الإعلانات تتكتب بالطريقة اللي المصري بينطقها،
عشان الموديل ينطقها صح. القاموس قابل للتعديل من غير لمس الكود.
"""
from __future__ import annotations

import re

# كلمات أجنبية/شائعة → كتابة عربية قريبة من النطق المصري
PRONUNCIATION: dict[str, str] = {
    # براندات وسوشيال
    "whatsapp": "واتساب",
    "facebook": "فيسبوك",
    "instagram": "إنستجرام",
    "youtube": "يوتيوب",
    "tiktok": "تيك توك",
    "google": "جوجل",
    # كلمات إعلانية
    "meeting": "ميتينج",
    "delivery": "دليفري",
    "order": "أوردر",
    "discount": "ديسكاونت",
    "online": "أونلاين",
    "offline": "أوفلاين",
    "offer": "أوفر",
    "call center": "كول سنتر",
    "promo code": "برومو كود",
    "brand": "براند",
    "premium": "بريميوم",
    "free": "فري",
    "open": "أوبن",
    "click": "كليك",
    "link": "لينك",
    "app": "آب",
    # مقاسات/مصطلحات
    "size": "سايز",
    "sale": "سيل",
    "new": "نيو",
}

# وحدات ملزوقة بالأرقام: 5kg → 5 كيلوجرام
UNITS: dict[str, str] = {
    "km": "كيلومتر",
    "kg": "كيلوجرام",
    "cm": "سنتيمتر",
    "mm": "مليمتر",
    "ml": "مللي",
    "gb": "جيجا",
    "mb": "ميجا",
    "kb": "كيلوبايت",
}

_WORDCHARS = r"0-9A-Za-z_\u0600-\u06FF"


def apply_lexicon(text: str) -> str:
    """يستبدل الكلمات الأجنبية بكتابة عربية بالنطق المصري."""
    out = text
    # العبارات الأطول الأول
    for term in sorted(PRONUNCIATION, key=len, reverse=True):
        pattern = rf"(?<![{_WORDCHARS}]){re.escape(term)}(?![{_WORDCHARS}])"
        out = re.sub(pattern, PRONUNCIATION[term], out, flags=re.IGNORECASE)
    return out


_UNIT_ATTACHED = re.compile(
    r"(?<=\d)\s*(" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def expand_units(text: str) -> str:
    """يفصل الوحدات الملزوقة بالأرقام عشان تتوسّع بعدها."""
    return _UNIT_ATTACHED.sub(lambda m: " " + UNITS[m.group(1).lower()], text)
