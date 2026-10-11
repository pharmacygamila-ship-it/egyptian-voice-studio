"""اختبارات فاحص النطق (ASR + مقارنة) — الجزء النقي بدون تحميل موديل.

    .venv\\Scripts\\python.exe tests\\test_qa.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from backend.qa.asr_check import compare, normalize_ar, strip_diacritics  # noqa: E402

ok = True
total = 0


def check(label: str, cond: bool) -> None:
    global ok, total
    total += 1
    ok = ok and cond
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")


def types(rep: dict) -> list[str]:
    return [it["type"] for it in rep["issues"]]


# ── 1) التطبيع للمقارنة ──────────────────────────────────────────────────
check("strip_diacritics", strip_diacritics("أَهْلًا") == "أهلا")
check("normalize_ar: تشكيل", normalize_ar("مِتِين وخَمْسِين") == "متين وخمسين")
check("normalize_ar: همزات", normalize_ar("أحمد إبراهيم آدم") == "احمد ابراهيم ادم")
check("normalize_ar: تاء مربوطة", normalize_ar("قهوة") == "قهوه")
check("normalize_ar: ألف مقصورة", normalize_ar("مصطفى") == "مصطفي")
check("normalize_ar: ترقيم عربي", normalize_ar("النهاردة، وبس!") == "النهارده وبس")
check("normalize_ar: لاتيني/رموز", normalize_ar("خصم 25%") == "خصم")

# ── 2) التطابق الكامل ────────────────────────────────────────────────────
rep = compare("قهوة بون النهاردة", "قهوة بون النهارده")
check("تطابق كامل: مفيش أخطاء", rep["issues"] == [])
check("تطابق كامل: النسبة 100%", rep["ratio"] == 1.0)

# ── 3) حرف ناقص ─────────────────────────────────────────────────────────
rep = compare("وريحة تجنن", "وريحه جنن")
check("حرف ناقص: اتكشف", len(rep["issues"]) == 1)
check("حرف ناقص: نوعه 'خطأ'", rep["issues"][0]["type"] == "خطأ")
check("حرف ناقص: التفصيل فيه -ت", "-ت" in rep["issues"][0]["detail"])

# ── 4) همزة وصل مقبولة (مش خطأ) ─────────────────────────────────────────
rep = compare("استوديو", "ستوديو")
check("همزة وصل: مقبولة", types(rep) == ["مقبول"])

# ── 5) كلمة زيادة ───────────────────────────────────────────────────────
rep = compare("قهوة بون", "قهوة ببون")
check("زيادة: اتكشفت", len(rep["issues"]) == 1)
check("زيادة: التفصيل +ب", "+ب" in rep["issues"][0]["detail"])

# ── 6) كلمات ناقصة ──────────────────────────────────────────────────────
rep = compare("طعم أصلي وريحة", "طعم أصلي")
check("ناقص: كلمة كاملة", rep["ratio"] < 1.0 and len(rep["issues"]) >= 1)

print(f"\n==> {total} اختبار |", "كله تمام ✅" if ok else "فيه فشل ❌")
raise SystemExit(0 if ok else 1)
