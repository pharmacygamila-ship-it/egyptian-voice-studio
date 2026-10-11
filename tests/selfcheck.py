"""فحص سريع إن مكونات المشروع شغالة (من غير شبكة).

    .venv\\Scripts\\python.exe tests\\selfcheck.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:  # يخلي الطبع UTF-8 على كونسول ويندوز
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from backend.audio.postprocess import postprocess  # noqa: E402
from backend.engine.base import SynthRequest  # noqa: E402
from backend.engine.remote_voicetut import RemoteVoiceTutEngine  # noqa: E402
from backend.text.normalize import normalize_egyptian, split_sentences  # noqa: E402

ok = True


def check(label: str, cond: bool) -> None:
    global ok
    ok = ok and cond
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")


# 1) تطبيع النص
sample = "خصم ٥٠٪ النهاردة & بكرة، اتصل على 0100  @  الفرع"
norm = normalize_egyptian(sample)
check("normalize: تحويل الأرقام الشرقية", normalize_egyptian("٥٠", numbers=False) == "50")
check("normalize: الرقم اتكتب حروف", "خمسين" in norm and "50" not in norm)
check("normalize: الرمز & اتحوّل", "&" not in norm and "و" in norm)
check("normalize: مسافات متعددة اتظبطت", "  " not in norm)
check("normalize: النسبة اتكتبت كلام", "في المية" in norm and "٪" not in norm)
print("    ->", norm.encode("unicode_escape").decode())

# 2) تقطيع الجُمل
sent = split_sentences("الجملة الأولى. الجملة التانية! والجملة التالتة؟", max_chars=15)
check("split_sentences", len(sent) == 3)

# 3) المحرك + لستة الأصوات
engine = RemoteVoiceTutEngine()
speakers = engine.list_speakers()
check("عدد الأصوات = 17", len(speakers) == 17)
check("Sayed موجود", any(s.name == "Sayed" for s in speakers))

# 4) استنساخ بدون مرجع يرفع خطأ
try:
    engine.clone(SynthRequest(text="x"), "x.wav")
    check("clone يرفض بدون ref_audio", False)
except ValueError:
    check("clone يرفض بدون ref_audio", True)

# 5) معالجة الصوت على العينة الموجودة
sample_wav = os.path.join("data", "outputs", "ads_sample_01_Sayed.wav")
if os.path.exists(sample_wav):
    out = os.path.join("data", "outputs", "ads_sample_01_Sayed_pp.wav")
    postprocess(sample_wav, out)
    check("postprocess اشتغلت", os.path.getsize(out) > 1000)
else:
    print("[SKIP] مفيش عينة للاختبار")

print("\n==>", "كله تمام ✅" if ok else "فيه فشل ❌")
raise SystemExit(0 if ok else 1)
