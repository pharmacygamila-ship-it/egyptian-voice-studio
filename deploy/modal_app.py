"""نشر الـ API على Modal (GPU serverless — رصيد مجاني $30/شهر).

الخطوات:
    pip install modal
    modal setup                                   # تسجيل دخول أول مرة
    modal secret create tts-token TTS_SERVER_TOKEN=اكتب-سرّ-طويل
    modal deploy deploy/modal_app.py

هيرجّعلك رابط زي:
    https://<workspace>--egyptian-tts-api.modal.run

وعلى جهازك تعيّن:
    TTS_ENGINE=server
    TTS_SERVER_URL=https://<workspace>--egyptian-tts-api.modal.run
    TTS_SERVER_TOKEN=نفس-السرّ

ملاحظة: الصورة بتضم مجلد `backend/` من الريبو (طبقة النص المصري + معالجة الصوت)
عشان النتيجة على Modal تطابق الـ API الرئيسي: تطبيع + تشكيل + LUFS/postprocess.
"""
from __future__ import annotations

import os

import modal

MODEL_ID = "mohammedaly22/VoiceTut-TTS"
HF_HOME = "/models"

# مسار `backend/` جوه الريبو — بننسخه للصورة عشان نستخدم نفس الطبقات (نص/صوت)
_BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")

SPEAKERS = [
    "Abdelrahman", "Abdullah", "Kamal", "Hossam", "Mohamed", "Omar",
    "Sayed", "Zaki", "Aly", "Essam", "Ahmed",
    "Asmaa", "Esraa", "Hanan", "Sarah", "Yasmin", "Omnia",
]

app = modal.App("egyptian-tts")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .copy_local_dir(_BACKEND, "/app/backend")
    .pip_install("torch")                                     # Modal بتجهّز نسخة CUDA
    .pip_install("git+https://github.com/k2-fsa/OmniVoice.git")
    .pip_install("voicetut-tts")
    .pip_install("fastapi", "uvicorn", "python-multipart", "soundfile", "numpy", "scipy", "pyloudnorm")
    .env({"HF_HOME": HF_HOME, "TTS_ENGINE": "local",
          "TTS_OUTPUT_DIR": "/tmp/outputs", "PYTHONPATH": "/app"})
)


def _download_weights() -> None:
    """تحميل الأوزان وقت بناء الصورة (مرة واحدة) لتقليل زمن الإقلاع."""
    from voicetut_tts import VoiceTutTTS

    VoiceTutTTS.from_pretrained(MODEL_ID)


image = image.run_function(_download_weights, timeout=1800)


@app.cls(
    image=image,
    gpu="T4",                 # الأرخص — استبدلها بـ "L4" أو "A10G" لسرعة أعلى
    scaledown_window=300,     # يفضل دافي 5 دقايق بعد آخر طلب
    timeout=600,
    secrets=[modal.Secret.from_name("tts-token")],
)
class VoiceServer:
    @modal.enter()            # مرة واحدة لكل حاوية
    def load(self) -> None:
        from voicetut_tts import VoiceTutTTS

        self.tts = VoiceTutTTS.from_pretrained(MODEL_ID)

    @modal.asgi_app()         # endpoint عام
    def api(self):
        import os
        import uuid

        from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
        from fastapi.responses import FileResponse
        from pydantic import BaseModel

        from backend.audio.export import export, media_type
        from backend.audio.postprocess import postprocess
        from backend.text.normalize import normalize_for_tts

        out_dir = "/tmp/outputs"
        os.makedirs(out_dir, exist_ok=True)
        fast = FastAPI(title="Egyptian TTS (Modal)", version="0.1.0")

        def require_token(x_auth_token: str | None = Header(default=None)) -> None:
            expected = os.getenv("TTS_SERVER_TOKEN")
            if expected and x_auth_token != expected:
                raise HTTPException(status_code=401, detail="توكن غير صحيح")

        class Body(BaseModel):
            text: str
            speaker: str = "Sayed"
            steps: int = 64
            guidance: float = 2.5
            speed: float = 0.95
            normalize: bool = True
            diacritics: bool = False
            postprocess: bool = True
            lufs: float = -14.0
            multiband: str | None = None
            fmt: str = "wav"

        @fast.get("/health")
        def health() -> dict:
            return {"ok": True, "engine": "modal-local"}

        @fast.get("/voices")
        def voices() -> list[dict]:
            return [{"name": s, "gender": "", "tags": []} for s in SPEAKERS]

        @fast.post("/tts", dependencies=[Depends(require_token)])
        def tts(body: Body) -> FileResponse:
            out = os.path.join(out_dir, f"{uuid.uuid4().hex[:8]}.wav")
            text = (
                normalize_for_tts(body.text, diacritics=body.diacritics)
                if body.normalize else body.text
            )
            self.tts.synthesize(
                text, speaker=body.speaker, output=out,
                num_step=body.steps, guidance_scale=body.guidance, speed=body.speed,
                normalize=False,
            )
            if body.postprocess:
                out = postprocess(out, target_lufs=body.lufs, multiband=body.multiband)
            out = export(out, body.fmt)
            return FileResponse(out, media_type=media_type(out), filename=os.path.basename(out))

        @fast.post("/clone", dependencies=[Depends(require_token)])
        async def clone(
            text: str = Form(...),
            ref_audio: UploadFile = File(...),
            ref_text: str = Form(""),
            steps: int = Form(64),
            guidance: float = Form(2.5),
            speed: float = Form(0.95),
            normalize: bool = Form(True),
            diacritics: bool = Form(False),
            postprocess_out: bool = Form(True),
            lufs: float = Form(-14.0),
            multiband: str | None = Form(None),
            fmt: str = Form("wav"),
        ) -> FileResponse:
            ref = os.path.join(out_dir, f"ref_{uuid.uuid4().hex[:8]}.wav")
            with open(ref, "wb") as fh:
                fh.write(await ref_audio.read())
            out = os.path.join(out_dir, f"{uuid.uuid4().hex[:8]}.wav")
            text = (
                normalize_for_tts(text, diacritics=diacritics)
                if normalize else text
            )
            self.tts.synthesize(
                text, ref_audio=ref, ref_text=ref_text, output=out,
                num_step=steps, guidance_scale=guidance, speed=speed,
                normalize=False,
            )
            if postprocess_out:
                out = postprocess(out, target_lufs=lufs, multiband=multiband)
            out = export(out, fmt)
            return FileResponse(out, media_type=media_type(out), filename=os.path.basename(out))

        return fast
