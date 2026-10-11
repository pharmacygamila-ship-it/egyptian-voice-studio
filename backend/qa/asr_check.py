"""فاحص النطق التلقائي: يفرّغ الصوت (ASR) ويقارنه بالنص الأصلي.

الهدف: كشف الأحرف الزيادة/الناقصة والنطق الغلط **موضوعيًا** بدل التخمين.

    from backend.qa.asr_check import check
    rep = check("out.wav", "قهوة بون النهاردة")
    print(rep["ratio"], rep["issues"])

على السطر:
    .venv\\Scripts\\python.exe -m backend.qa.asr_check out.wav "النص الأصلي"

ملاحظة: يستخدم faster-whisper محلي (CPU) — أول تشغيل بينزّل الموديل.
"""
from __future__ import annotations

import argparse
import difflib
import math
import os
import re
import sys
from typing import Any, Optional

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

DEFAULT_MODEL = os.getenv("ASR_MODEL", "large-v3")

# تشكيل + تطويل + علامات
_DIACRITICS = set(
    "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0653\u0654\u0655\u0670\u0640"
)
_ALEF = "أإآٱ"
_AR_KEEP = re.compile(r"[^\u0621-\u064A\u0671-\u06D3\s]+")

_MODEL: Optional[Any] = None
_MODEL_NAME: Optional[str] = None


def strip_diacritics(text: str) -> str:
    return "".join(ch for ch in text if ch not in _DIACRITICS)


def normalize_ar(text: str) -> str:
    """تطبيع للمقارنة: شيل التشكيل/الترقيم وتوحيد الهمزات والتاء المربوطة."""
    text = strip_diacritics(text)
    text = text.replace("\u0640", "")
    text = _AR_KEEP.sub(" ", text)
    for a in _ALEF:
        text = text.replace(a, "\u0627")
    text = text.replace("\u0649", "\u064a").replace("\u0629", "\u0647")
    return re.sub(r"\s+", " ", text).strip()


def _load_audio(path: str, sr_out: int = 16000) -> np.ndarray:
    data, sr = sf.read(path, always_2d=False, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != sr_out:
        g = math.gcd(int(sr), sr_out)
        data = resample_poly(data, sr_out // g, int(sr) // g)
    return np.ascontiguousarray(data, dtype=np.float32)


def transcribe(path: str, model_size: str = DEFAULT_MODEL) -> str:
    """يفرّغ ملف صوتي لنص عربي (ASR محلي)."""
    global _MODEL, _MODEL_NAME
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "محتاج faster-whisper: pip install faster-whisper"
        ) from exc

    if _MODEL is None or _MODEL_NAME != model_size:
        device = os.getenv("ASR_DEVICE", "cpu")
        compute = os.getenv("ASR_COMPUTE", "int8")
        _MODEL = WhisperModel(model_size, device=device, compute_type=compute)
        _MODEL_NAME = model_size

    segments, _ = _MODEL.transcribe(
        _load_audio(path), language="ar", beam_size=5, vad_filter=True
    )
    return "".join(seg.text for seg in segments).strip()


def _char_diff(ref: str, hyp: str) -> str:
    """فرق على مستوى الحروف لكلمتين (للتوضيح)."""
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ref, b=hyp).get_opcodes():
        if tag == "replace":
            ops.append(f"{ref[i1:i2]}→{hyp[j1:j2]}")
        elif tag == "delete":
            ops.append(f"-{ref[i1:i2]}")
        elif tag == "insert":
            ops.append(f"+{hyp[j1:j2]}")
    return " ".join(ops)


def compare(reference: str, heard: str) -> dict:
    """يقارن النص الأصلي بالمتفَرّغ، ويرجّع نسبة التشابه والأخطاء."""
    ref = normalize_ar(reference).split()
    hyp = normalize_ar(heard).split()
    sm = difflib.SequenceMatcher(a=ref, b=hyp)
    issues = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        r_words, h_words = ref[i1:i2], hyp[j1:j2]
        kind = {"replace": "خطأ", "delete": "ناقص", "insert": "زيادة"}[tag]
        detail = ""
        if len(r_words) == len(h_words) == 1:
            a, b = r_words[0], h_words[0]
            if a == "\u0627" + b or b == "\u0627" + a:
                kind, detail = "مقبول", "همزة وصل"
            else:
                detail = _char_diff(a, b)
        issues.append({"type": kind, "ref": " ".join(r_words), "heard": " ".join(h_words), "detail": detail})
    return {
        "ratio": round(sm.ratio(), 4),
        "reference": " ".join(ref),
        "heard": " ".join(hyp),
        "issues": issues,
    }


def check(audio_path: str, reference: str, model_size: str = DEFAULT_MODEL) -> dict:
    """يفرّغ الصوت ويقارنه بالنص المرجعي."""
    heard = transcribe(audio_path, model_size=model_size)
    rep = compare(reference, heard)
    rep["audio"] = audio_path
    return rep


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description="فاحص نطق (ASR + مقارنة)")
    ap.add_argument("audio", help="ملف الصوت")
    ap.add_argument("reference", help="النص الأصلي المتوقع")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="حجم موديل whisper")
    args = ap.parse_args()

    rep = check(args.audio, args.reference, args.model)
    print(f"نسبة التطابق: {rep['ratio'] * 100:.1f}%")
    print(f"المتوقّع : {rep['reference']}")
    print(f"المسموع : {rep['heard']}")
    if not rep["issues"]:
        print("✅ مفيش أخطاء ظاهرة")
    else:
        print("⚠️ الأخطاء:")
        for it in rep["issues"]:
            extra = f"  [{it['detail']}]" if it["detail"] else ""
            print(f"  - {it['type']}: «{it['ref']}» → «{it['heard']}»{extra}")
    return 0 if not rep["issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
