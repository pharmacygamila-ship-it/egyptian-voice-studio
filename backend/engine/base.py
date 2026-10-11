"""الواجهة المشتركة لكل محرّكات الصوت.

الفكرة: الكود بتاع التطبيق يتعامل مع `TTSEngine` بس، والمحرك الفعلي
يتغيّر من غير ما نلمس باقي المشروع:

    RemoteVoiceTutEngine  → الـ Space الجاهز أونلاين (PoC، من غير GPU)
    LocalVoiceTutEngine   → تشغيل محلي/سحابي على GPU
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Speaker:
    """بيانات صوت جاهز."""

    name: str
    gender: str = "unknown"          # "ذكر" / "أنثى"
    tags: list[str] = field(default_factory=list)   # زي: حماسي، هادي، شبابي


@dataclass
class SynthRequest:
    """طلب توليد صوت واحد."""

    text: str
    speaker: Optional[str] = None        # صوت جاهز بالاسم
    ref_audio: Optional[str] = None      # مسار ملف مرجعي (للاستنساخ)
    ref_text: Optional[str] = None       # نص المقطع المرجعي (اختياري)
    language: str = "العربية (Egyptian)"
    steps: int = 64                      # خطوات التوليد (8–64)
    guidance: float = 2.5                # قوة التوجيه (1.0–5.0)
    speed: float = 0.95                  # السرعة (0.5–2.0)
    normalize: bool = True               # تطبيع النص
    style: Optional[str] = None          # وسم أداء (اختياري)


class TTSEngine(ABC):
    """محرك TTS مجرد."""

    name: str = "base"

    @abstractmethod
    def list_speakers(self) -> list[Speaker]:
        """يرجّع الأصوات الجاهزة المتاحة."""

    @abstractmethod
    def synthesize(self, req: SynthRequest, out_path: str) -> str:
        """يولّد الصوت ويحفظه في `out_path`، ويرجّع المسار النهائي."""

    def clone(self, req: SynthRequest, out_path: str) -> str:
        """استنساخ صوت من مقطع مرجعي (افتراضياً نفس مسار التوليد)."""
        if not req.ref_audio:
            raise ValueError("لازم توفّر مقطع مرجعي (ref_audio) للاستنساخ")
        return self.synthesize(req, out_path)
