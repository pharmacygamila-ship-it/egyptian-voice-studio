"""محرك VoiceTut-TTS محلياً (GPU) — للإنتاج.

مش مثبّت افتراضياً لأن الجهاز الحالي مالوش كارت NVIDIA.
لما يتوفر GPU، شغّل:

    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install git+https://github.com/k2-fsa/OmniVoice.git
    pip install voicetut-tts

وبعدها الكود ده هيشتغل زي الـ Remote بس أسرع وبكوتة مفتوحة.
"""
from __future__ import annotations

from .base import Speaker, SynthRequest, TTSEngine
from .remote_voicetut import _BUILTIN


class LocalVoiceTutEngine(TTSEngine):
    name = "local-voicetut"

    def __init__(self, model_id: str = "mohammedaly22/VoiceTut-TTS", device: str = "cuda") -> None:
        try:
            from voicetut_tts import VoiceTutTTS  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "حزمة voicetut-tts مش مثبّتة. شوف requirements.txt "
                "(قسم GPU) ثم أعد المحاولة."
            ) from exc
        self.tts = VoiceTutTTS.from_pretrained(model_id)
        self.device = device

    def list_speakers(self) -> list[Speaker]:
        return list(_BUILTIN.values())

    def synthesize(self, req: SynthRequest, out_path: str) -> str:
        kwargs = dict(
            num_step=req.steps,
            guidance_scale=req.guidance,
            speed=req.speed,
            normalize=req.normalize,
        )
        if req.ref_audio:
            self.tts.synthesize(
                req.text,
                ref_audio=req.ref_audio,
                ref_text=req.ref_text or "",
                output=out_path,
                **kwargs,
            )
        else:
            self.tts.synthesize(
                req.text,
                speaker=req.speaker or "Sayed",
                output=out_path,
                **kwargs,
            )
        return out_path
