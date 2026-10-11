"""FastAPI backend لتطبيق استنساخ/توليد الصوت المصري.

التشغيل:
    .venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload --port 8000

المحرك الافتراضي = الـ Space الأونلاين (من غير GPU).
لتبديله لمحرك محلي: عيّن TTS_ENGINE=local
"""
from __future__ import annotations

import os
import uuid

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.audio.postprocess import postprocess
from backend.engine.base import SynthRequest, TTSEngine
from backend.engine.remote_voicetut import RemoteVoiceTutEngine
from backend.text.normalize import normalize_egyptian

OUTPUT_DIR = os.getenv("TTS_OUTPUT_DIR", os.path.join("data", "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


def require_token(x_auth_token: str | None = Header(default=None)) -> None:
    """يحمي الـ endpoints لو TTS_SERVER_TOKEN متعيّن."""
    expected = os.getenv("TTS_SERVER_TOKEN")
    if expected and x_auth_token != expected:
        raise HTTPException(status_code=401, detail="توكن غير صحيح")


def _build_engine() -> TTSEngine:
    which = os.getenv("TTS_ENGINE", "remote").lower()
    if which == "local":
        from backend.engine.local_voicetut import LocalVoiceTutEngine

        return LocalVoiceTutEngine()
    if which == "server":
        from backend.engine.server_client import ServerVoiceTutEngine

        return ServerVoiceTutEngine()
    return RemoteVoiceTutEngine()


engine = _build_engine()
app = FastAPI(title="Egyptian Voice Clone API", version="0.1.0")


class TTSBody(BaseModel):
    text: str = Field(..., min_length=1)
    speaker: str = "Sayed"
    language: str = "العربية (Egyptian)"
    steps: int = Field(64, ge=8, le=64)
    guidance: float = Field(2.5, ge=1.0, le=5.0)
    speed: float = Field(0.95, ge=0.5, le=2.0)
    normalize: bool = True
    postprocess: bool = True


@app.get("/health")
def health() -> dict:
    return {"ok": True, "engine": engine.name}


@app.get("/voices")
def voices() -> list[dict]:
    return [s.__dict__ for s in engine.list_speakers()]


@app.post("/tts", dependencies=[Depends(require_token)])
def tts(body: TTSBody) -> FileResponse:
    text = normalize_egyptian(body.text) if body.normalize else body.text
    out = os.path.join(OUTPUT_DIR, f"tts_{uuid.uuid4().hex[:8]}.wav")
    req = SynthRequest(
        text=text,
        speaker=body.speaker,
        language=body.language,
        steps=body.steps,
        guidance=body.guidance,
        speed=body.speed,
        normalize=body.normalize,
    )
    try:
        path = engine.synthesize(req, out)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if body.postprocess:
        path = postprocess(path)
    return FileResponse(path, media_type="audio/wav", filename=os.path.basename(path))


@app.post("/clone", dependencies=[Depends(require_token)])
async def clone(
    text: str = Form(...),
    ref_audio: UploadFile = File(...),
    ref_text: str = Form(""),
    steps: int = Form(64),
    guidance: float = Form(2.5),
    speed: float = Form(0.95),
    postprocess_out: bool = Form(True),
) -> FileResponse:
    ref_path = os.path.join(OUTPUT_DIR, f"ref_{uuid.uuid4().hex[:8]}.wav")
    with open(ref_path, "wb") as fh:
        fh.write(await ref_audio.read())

    out = os.path.join(OUTPUT_DIR, f"clone_{uuid.uuid4().hex[:8]}.wav")
    req = SynthRequest(
        text=normalize_egyptian(text),
        ref_audio=ref_path,
        ref_text=ref_text,
        steps=steps,
        guidance=guidance,
        speed=speed,
    )
    try:
        path = engine.clone(req, out)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if postprocess_out:
        path = postprocess(path)
    return FileResponse(path, media_type="audio/wav", filename=os.path.basename(path))
