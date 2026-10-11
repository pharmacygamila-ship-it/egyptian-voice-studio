"""اختبارات طبقة النص المصري (أرقام + نطق + تنضيف).

    .venv\\Scripts\\python.exe tests\\test_text.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from backend.text.diacritics import apply_diacritics  # noqa: E402
from backend.text.lexicon import apply_lexicon, expand_units  # noqa: E402
from backend.text.normalize import normalize_egyptian  # noqa: E402
from backend.text.numbers import digits_to_words, expand_numbers, int_to_words  # noqa: E402

ok = True
total = 0


def check(label: str, cond: bool) -> None:
    global ok, total
    total += 1
    ok = ok and cond
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")


# ── 1) الأرقام → كلام مصري ───────────────────────────────────────────────
NUM_CASES = {
    0: "صفر",
    1: "واحد",
    2: "اتنين",
    9: "تسعة",
    11: "حداشر",
    15: "خمستاشر",
    20: "عشرين",
    21: "واحد وعشرين",
    50: "خمسين",
    99: "تسعة وتسعين",
    100: "مية",
    126: "مية وستة وعشرين",
    200: "ميتين",
    500: "خمسمية",
    1000: "ألف",
    1500: "ألف وخمسمية",
    2000: "ألفين",
    3000: "تلاتة آلاف",
    11000: "حداشر ألف",
    2026: "ألفين وستة وعشرين",
    1000000: "مليون",
    2000000: "مليونين",
}
for value, expected in NUM_CASES.items():
    got = int_to_words(value)
    check(f"int_to_words({value}) = {expected}", got == expected)
    if got != expected:
        print(f"       -> جاب: {got}")

# ── 2) توسيع الأرقام داخل النص ───────────────────────────────────────────
check("expand: نسبة", expand_numbers("خصم 50 في المية") == "خصم خمسين في المية")
check("expand: سنة", expand_numbers("سنة 2026") == "سنة ألفين وستة وعشرين")
check("expand: عشرية", expand_numbers("3.5") == "تلاتة فاصلة خمسة")
check("expand: وقت", expand_numbers("3:30") == "تلاتة وتلاتين")
check("expand: فاصلة آلاف", expand_numbers("1,000 جنيه") == "ألف جنيه")
check(
    "expand: تليفون رقم رقم",
    expand_numbers("01001234567")
    == "صفر واحد صفر صفر واحد اتنين تلاتة أربعة خمسة ستة سبعة",
)
check("digits_to_words مباشر", digits_to_words("22") == "اتنين اتنين")

# ── 3) قاموس النطق ───────────────────────────────────────────────────────
check("lexicon: واتساب", apply_lexicon("كلمني على WhatsApp") == "كلمني على واتساب")
check("lexicon: أوردر", apply_lexicon("اعمل order حالا") == "اعمل أوردر حالا")
check("lexicon: مبيغيّرش جوه كلمة", apply_lexicon("freezer") == "freezer")
check("units: 5kg", expand_units("5kg سكر") == "5 كيلوجرام سكر")

# ── 4) الدمج الكامل في normalize ─────────────────────────────────────────
check("normalize: نسبة بالكلام", normalize_egyptian("خصم ٥٠٪") == "خصم خمسين في المية")
check("normalize: إيموجي اتشال", normalize_egyptian("عرض 🔥🔥 جامد") == "عرض جامد")
check("normalize: تطويل الحروف", normalize_egyptian("حلووووو جدا") == "حلو جدا")
check(
    "normalize: الإنجليزي بالنطق المصري",
    normalize_egyptian("الطلب من WhatsApp") == "الطلب من واتساب",
)
check("normalize: وحدة ملزوقة", normalize_egyptian("5kg سكر") == "خمسة كيلوجرام سكر")

# إطفاء الخصائص يرجع السلوك القديم
check("normalize: numbers=False", normalize_egyptian("٥٠ جنيه", numbers=False) == "50 جنيه")
check(
    "normalize: use_lexicon=False",
    normalize_egyptian("WhatsApp", use_lexicon=False) == "WhatsApp",
)

# ── 5) براندات وشركات ────────────────────────────────────────────────────
check("lexicon: بيبسي", apply_lexicon("اشرب Pepsi") == "اشرب بيبسي")
check("lexicon: فودافون", apply_lexicon("عرض من Vodafone") == "عرض من فودافون")
check("lexicon: ماكدونالدز", apply_lexicon("McDonald's") == "ماكدونالدز")
check("lexicon: طلبات", apply_lexicon("اطلب من Talabat") == "اطلب من طلبات")

# ── 6) التشكيل (opt-in) ──────────────────────────────────────────────────
check("diacritics: عرض", apply_diacritics("عرض خاص") == "عَرْض خاص")
check("diacritics: خصم", apply_diacritics("خصم 50") == "خَصْم 50")
check(
    "normalize: diacritics=True",
    normalize_egyptian("خصم 50", diacritics=True) == "خَصْم خمسين",
)
check(
    "normalize: diacritics مقفول افتراضياً",
    normalize_egyptian("خصم 50") == "خصم خمسين",
)

print(f"\n==> {total} اختبار |", "كله تمام ✅" if ok else "فيه فشل ❌")
raise SystemExit(0 if ok else 1)
