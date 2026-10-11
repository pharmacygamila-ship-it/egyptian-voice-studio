"""اختيار المحرك حسب إعداد TTS_ENGINE (مكان واحد لكل المشروع)."""
from __future__ import annotations

import os

from .base import TTSEngine


def build_engine(kind: str | None = None, **kwargs) -> TTSEngine:
    """يبني المحرك المناسب: remote | server | local."""
    kind = (kind or os.getenv("TTS_ENGINE", "remote")).lower()

    if kind == "local":
        from .local_voicetut import LocalVoiceTutEngine

        return LocalVoiceTutEngine(**kwargs)
    if kind == "server":
        from .server_client import ServerVoiceTutEngine

        return ServerVoiceTutEngine(**kwargs)
    if kind == "remote":
        from .remote_voicetut import RemoteVoiceTutEngine

        return RemoteVoiceTutEngine(**kwargs)
    raise ValueError(f"محرك غير معروف: {kind!r} (المتاح: remote | server | local)")
