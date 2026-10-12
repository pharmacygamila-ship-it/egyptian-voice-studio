"""FastAPI backend لتطبيق استنساخ/توليد الصوت المصري.

ده **سيرفر الموديل**: بيشتغل على GPU (مثلاً Colab)، والتطبيق يتصل بيه بمفتاح.

التشغيل محلياً:
    .venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload --port 8000

التشغيل كسيرفر سحابي (Colab): شوف deploy/colab_model_server.ipynb

المفتاح: لو عيّنت TTS_SERVER_TOKEN، لازم كل الطلبات تبعته في هيدر `X-Auth-Token`.
المحرك الافتراضي = الـ Space الأونلاين (من غير GPU). للـ GPU: عيّن TTS_ENGINE=local
"""
from __future__ import annotations

import os
import uuid

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.audio.export import export, media_type
from backend.audio.postprocess import postprocess
from backend.engine.base import SynthRequest, TTSEngine
from backend.engine.factory import build_engine
from backend.text.normalize import normalize_for_tts

OUTPUT_DIR = os.getenv("TTS_OUTPUT_DIR", os.path.join("data", "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


def require_token(x_auth_token: str | None = Header(default=None)) -> None:
    """يحمي الـ endpoints لو TTS_SERVER_TOKEN متعيّن."""
    expected = os.getenv("TTS_SERVER_TOKEN")
    if expected and x_auth_token != expected:
        raise HTTPException(status_code=401, detail="توكن غير صحيح")


# الموديل بيتحمّل عند أول استخدام، مش وقت بدء السيرفر — كده السيرفر بيرد فورًا
# على /health والنفق العام بيطلع بسرعة، وتحميل الموديل (~2.5GB) بيحصل في /warmup
# أو أول توليد (من غير ما يخلّي الشكل يوحي إن السيرفر واقع وبطيء).
_engine: TTSEngine | None = None


def get_engine() -> TTSEngine:
    """يرجّع المحرك (ويبنيه مرة واحدة عند أول استخدام)."""
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


app = FastAPI(title="Egyptian Voice Clone API", version="0.1.0")

# يسمح لواجهة ويب في نطاق تاني (أو للتجربة) إنها تكلّم السيرفر ده.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TTSBody(BaseModel):
    text: str = Field(..., min_length=1)
    speaker: str = "Sayed"
    language: str = "العربية (Egyptian)"
    steps: int = Field(64, ge=8, le=64)
    guidance: float = Field(2.5, ge=1.0, le=5.0)
    speed: float = Field(0.95, ge=0.5, le=2.0)
    normalize: bool = True
    diacritics: bool = Field(False, description="تشكيل الكلمات الملتبسة (اختياري)")
    postprocess: bool = True
    lufs: float = Field(-14.0, ge=-24.0, le=-6.0, description="جهارة الهدف (EBU R128)")
    multiband: str | None = Field(
        None, description="ضغط متعدد النطاقات: voice / warm / punch / broadcast"
    )
    fmt: str = Field("wav", description="صيغة الناتج: wav أو mp3")
    target_sr: int | None = Field(
        None, ge=8000, le=48000, description="إعادة تنميط الإخراج (مثلاً 48000 للإنتاج)"
    )
    mp3_bitrate: int = Field(192, ge=96, le=320, description="معدل بت MP3 (نفس جودة أعلى)")


@app.get("/health")
def health() -> dict:
    kind = (os.getenv("TTS_ENGINE") or "remote").lower()
    return {
        "ok": True,
        "engine": _engine.name if _engine is not None else kind,
        "model": os.getenv("TTS_MODEL", ""),
        "loaded": _engine is not None,
        "auth_required": bool(os.getenv("TTS_SERVER_TOKEN")),
        "version": app.version,
    }


FRONTEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "index.html"
)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    if not os.path.exists(FRONTEND):
        raise HTTPException(status_code=404, detail="الواجهة غير موجودة")
    return FileResponse(FRONTEND, media_type="text/html")


@app.get("/voices")
def voices() -> list[dict]:
    # قائمة الأصوات ثابتة جوه كل المحركات — بنرجّعها من غير ما نحمّل الموديل
    # (عشان «اختبار الاتصال» في التطبيق يبقى سريع وزيه زي السيرفر).
    if _engine is not None:
        return [s.__dict__ for s in _engine.list_speakers()]
    from backend.engine.remote_voicetut import _BUILTIN

    return [s.__dict__ for s in _BUILTIN.values()]


@app.post("/warmup", dependencies=[Depends(require_token)])
def warmup() -> dict:
    """يحمّل الموديل مسبقًا (اختياري) عشان أول طلب من التطبيق يبقى سريع."""
    eng = get_engine()
    out = os.path.join(OUTPUT_DIR, "warmup.wav")
    req = SynthRequest(text="تجهيز", speaker="Sayed", steps=8, normalize=False)
    try:
        eng.synthesize(req, out)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "engine": eng.name}


def _finish(path: str, fmt: str, *, bitrate: int = 192) -> FileResponse:
    """يصدّر للصيغة المطلوبة (wav/mp3) ويرجّع الملف."""
    try:
        path = export(path, fmt, bitrate=bitrate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(path, media_type=media_type(path), filename=os.path.basename(path))


@app.post("/tts", dependencies=[Depends(require_token)])
def tts(body: TTSBody) -> FileResponse:
    if body.normalize:
        text = normalize_for_tts(body.text, diacritics=body.diacritics)
    else:
        text = body.text
    out = os.path.join(OUTPUT_DIR, f"tts_{uuid.uuid4().hex[:8]}.wav")
    req = SynthRequest(
        text=text,
        speaker=body.speaker,
        language=body.language,
        steps=body.steps,
        guidance=body.guidance,
        speed=body.speed,
        normalize=False,
    )
    try:
        path = get_engine().synthesize(req, out)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if body.postprocess:
        path = postprocess(
            path,
            target_lufs=body.lufs,
            multiband=body.multiband,
            target_sr=body.target_sr,
        )
    return _finish(path, body.fmt, bitrate=body.mp3_bitrate)


@app.post("/clone", dependencies=[Depends(require_token)])
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
    target_sr: int | None = Form(None),
    mp3_bitrate: int = Form(192),
) -> FileResponse:
    ref_path = os.path.join(OUTPUT_DIR, f"ref_{uuid.uuid4().hex[:8]}.wav")
    with open(ref_path, "wb") as fh:
        fh.write(await ref_audio.read())

    out = os.path.join(OUTPUT_DIR, f"clone_{uuid.uuid4().hex[:8]}.wav")
    req = SynthRequest(
        text=normalize_for_tts(text, diacritics=diacritics) if normalize else text,
        ref_audio=ref_path,
        ref_text=ref_text,
        steps=steps,
        guidance=guidance,
        speed=speed,
        normalize=False,
    )
    try:
        path = get_engine().clone(req, out)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if postprocess_out:
        path = postprocess(
            path,
            target_lufs=lufs,
            multiband=multiband,
            target_sr=target_sr,
        )
    return _finish(path, fmt, bitrate=mp3_bitrate)
