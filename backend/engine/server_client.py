"""محرك بيبعت الشغل على سيرفر GPU بتاعنا (بدل الـ Space أو المحلي).

ده اللي بيخلّي تطبيقك المحلي (على الجهاز الضعيف) يستخدم GPU سحابي:
    TTS_ENGINE=server
    TTS_SERVER_URL=https://xxxx-8000.proxy.runpod.net
    TTS_SERVER_TOKEN=سرّي-كلمه-سرّية

السيرفر نفسه شغّال بنفس الموديل المفتوح (LocalVoiceTutEngine).
"""
from __future__ import annotations

import os
from typing import Optional

import requests

from .base import Speaker, SynthRequest, TTSEngine


class ServerVoiceTutEngine(TTSEngine):
    name = "server"

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 900,
    ) -> None:
        self.base = (base_url or os.getenv("TTS_SERVER_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.token = token or os.getenv("TTS_SERVER_TOKEN") or ""
        self.timeout = timeout
        self.session = requests.Session()
        if self.token:
            self.session.headers["X-Auth-Token"] = self.token

    def list_speakers(self) -> list[Speaker]:
        r = self.session.get(f"{self.base}/voices", timeout=30)
        r.raise_for_status()
        return [Speaker(**s) for s in r.json()]

    def synthesize(self, req: SynthRequest, out_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        if req.ref_audio:
            with open(req.ref_audio, "rb") as fh:
                files = {"ref_audio": (os.path.basename(req.ref_audio), fh, "audio/wav")}
                data = {
                    "text": req.text,
                    "ref_text": req.ref_text or "",
                    "steps": req.steps,
                    "guidance": req.guidance,
                    "speed": req.speed,
                }
                resp = self.session.post(
                    f"{self.base}/clone", files=files, data=data, timeout=self.timeout
                )
        else:
            payload = {
                "text": req.text,
                "speaker": req.speaker or "Sayed",
                "language": req.language,
                "steps": req.steps,
                "guidance": req.guidance,
                "speed": req.speed,
                "normalize": req.normalize,
            }
            resp = self.session.post(f"{self.base}/tts", json=payload, timeout=self.timeout)

        resp.raise_for_status()
        with open(out_path, "wb") as fh:
            fh.write(resp.content)
        return out_path
