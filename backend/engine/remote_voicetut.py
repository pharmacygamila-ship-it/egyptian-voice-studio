"""محرك VoiceTut-TTS عبر الـ HTTP API بتاع الـ HuggingFace Space.

مميزاته: يشتغل فوراً من غير GPU محلي ولا تحميل موديلات.
عيوبه:  الكوتة المجانية للـ Space محدودة (ZeroGPU)، فمش مناسب للإنتاج.

الاستخدام:
    client = RemoteVoiceTutEngine()
    client.synthesize(SynthRequest(text="...", speaker="Sayed"), "out.wav")

لو عندك HF token ارفعه في متغيّر البيئة HF_TOKEN عشان كوتة أعلى.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Optional

import requests

from .base import Speaker, SynthRequest, TTSEngine

DEFAULT_SPACE = "https://mohammedaly22-voicetut-tts.hf.space"

LANG_AR = "العربية (Egyptian)"
LANG_EN = "English"


def _read_hf_token_file() -> Optional[str]:
    """يقرأ توكن HF من مكانه القياسي (لو المستخدم عمل login قبل كده).

    يدعم: `huggingface_hub.get_token()`، ثم ملفات `token` في `HF_HOME`
    و `~/.cache/huggingface` و `~/.huggingface`.
    """
    try:
        from huggingface_hub import get_token  # type: ignore

        tok = get_token()
        if tok:
            return tok
    except Exception:  # noqa: BLE001 - المكتبة مش متثبّتة أو فشلت
        pass

    roots = []
    hf_home = os.getenv("HF_HOME")
    if hf_home:
        roots.append(hf_home)
    home = os.path.expanduser("~")
    roots += [
        os.path.join(home, ".cache", "huggingface"),
        os.path.join(home, ".huggingface"),
    ]
    for root in roots:
        path = os.path.join(root, "token")
        try:
            with open(path, encoding="utf-8") as fh:
                tok = fh.read().strip()
            if tok:
                return tok
        except OSError:
            continue
    return None

# بيانات الأصوات الجاهزة (الاسم → الجنس/الوسوم) — من كارت الموديل.
_BUILTIN: dict[str, Speaker] = {
    # ذكور
    "Abdelrahman": Speaker("Abdelrahman", "ذكر", ["محترف", "حماسي"]),
    "Abdullah": Speaker("Abdullah", "ذكر", ["رسمي", "محترف"]),
    "Kamal": Speaker("Kamal", "ذكر", ["رسمي", "وقور"]),
    "Hossam": Speaker("Hossam", "ذكر", ["حيوي"]),
    "Mohamed": Speaker("Mohamed", "ذكر", ["هادي", "عميق"]),
    "Omar": Speaker("Omar", "ذكر", ["شبابي"]),
    "Sayed": Speaker("Sayed", "ذكر", ["شبابي", "معبّر"]),
    "Zaki": Speaker("Zaki", "ذكر", ["هادي"]),
    "Aly": Speaker("Aly", "ذكر", ["رسمي"]),
    "Essam": Speaker("Essam", "ذكر", ["معبّر"]),
    "Ahmed": Speaker("Ahmed", "ذكر", ["حيوي"]),
    # إناث
    "Asmaa": Speaker("Asmaa", "أنثى", ["ناعم", "ودود"]),
    "Esraa": Speaker("Esraa", "أنثى", ["هاديه"]),
    "Hanan": Speaker("Hanan", "أنثى", ["رسميه"]),
    "Sarah": Speaker("Sarah", "أنثى", ["محترفه"]),
    "Yasmin": Speaker("Yasmin", "أنثى", ["شبابي", "مشرق"]),
    "Omnia": Speaker("Omnia", "أنثى", ["حيويه"]),
}


class RemoteVoiceTutEngine(TTSEngine):
    name = "remote-voicetut"

    def __init__(
        self,
        base_url: str = DEFAULT_SPACE,
        hf_token: Optional[str] = None,
        timeout: int = 600,
    ) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        token = (
            hf_token
            or os.getenv("HF_TOKEN")
            or os.getenv("HUGGING_FACE_HUB_TOKEN")
            or _read_hf_token_file()
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    # ── الداخل ──────────────────────────────────────────────────────────
    def _call(self, fn: str, data: list[Any]) -> list[Any]:
        """ينادي endpoint من الـ Gradio API ويرجّع الناتج (مع دعم SSE)."""
        r = self.session.post(
            f"{self.base}/gradio_api/call/{fn.lstrip('/')}",
            json={"data": data},
            timeout=60,
        )
        r.raise_for_status()
        event_id = r.json()["event_id"]

        with self.session.get(
            f"{self.base}/gradio_api/call/{fn.lstrip('/')}/{event_id}",
            stream=True,
            timeout=self.timeout,
        ) as s:
            event = None
            for raw in s.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                if raw.startswith("event:"):
                    event = raw.split(":", 1)[1].strip()
                elif raw.startswith("data:"):
                    payload = raw.split(":", 1)[1].strip()
                    if event == "complete":
                        return json.loads(payload)
                    if event == "error":
                        raise RuntimeError(
                            "الـ Space رجّع خطأ (غالباً الكوتة المجانية خلصت). "
                            "جرّب تاني بعد شوية أو استخدم HF_TOKEN، "
                            f"أو شغّل محلياً: {payload}"
                        )
        raise RuntimeError("البث خلص من غير نتيجة كاملة")

    def _download(self, file_data: dict, out_path: str) -> str:
        url = file_data.get("url") or file_data.get("path")
        if not url:
            raise RuntimeError(f"مفيش رابط للملف في الناتج: {file_data}")
        if url.startswith("/"):
            url = self.base + url
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with self.session.get(url, stream=True, timeout=self.timeout) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        return out_path

    def _upload(self, path: str) -> dict:
        """يرفع ملف صوتي للـ Space ويرجّع مرجع FileData."""
        with open(path, "rb") as fh:
            files = {"files": (os.path.basename(path), fh, "audio/wav")}
            r = self.session.post(
                f"{self.base}/gradio_api/upload",
                params={"upload_id": uuid.uuid4().hex},
                files=files,
                timeout=180,
            )
        r.raise_for_status()
        server_path = r.json()[0]
        return {"path": server_path, "meta": {"_type": "gradio.FileData"}}

    # ── الواجهة العامة ─────────────────────────────────────────────────
    def list_speakers(self) -> list[Speaker]:
        return list(_BUILTIN.values())

    def synthesize(self, req: SynthRequest, out_path: str) -> str:
        common = [req.text, req.language, req.steps, req.guidance, req.speed, req.normalize]
        if req.ref_audio:
            ref = self._upload(req.ref_audio)
            data = [ref, req.ref_text or "", *common]
            fn = "/run_c_oneshot"
        else:
            speaker = req.speaker or "Sayed"
            data = [speaker, *common]
            fn = "/run_b_oneshot"

        result = self._call(fn, data)
        if not result or not isinstance(result[0], dict):
            raise RuntimeError(f"ناتج غير متوقع: {result!r}")
        return self._download(result[0], out_path)
