"""تخزين الإعدادات + قاموس النطق المخصّص (ملفات JSON محلية).

الهدف: التطبيق يتحكّم في كل حاجة من جوّه نفسه — نوع المحرك، بيانات السيرفر،
وقاموس النطق — من غير ما المستخدم يلمس متغيّرات بيئة أو كود، ومن غير ما نلمس
الـ API أو الـ CLI (بيقرأوا نفس الحاجات).

الملفات (مش بتترفع على Git — فيها توكنات):
    data/app_settings.json   : إعدادات المحرك الافتراضية
    data/user_lexicon.json   : {الكلمة: النطق} اللي المستخدم ضافها
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.getenv("TTS_DATA_DIR", os.path.join(ROOT, "data"))
SETTINGS_PATH = os.path.join(DATA_DIR, "app_settings.json")
LEXICON_PATH = os.getenv("TTS_LEXICON", os.path.join(DATA_DIR, "user_lexicon.json"))

DEFAULT_SETTINGS: dict[str, Any] = {
    "engine": os.getenv("TTS_ENGINE", "remote"),
    "server_url": os.getenv("TTS_SERVER_URL", ""),
    "token": os.getenv("TTS_SERVER_TOKEN", ""),
    "model_id": "mohammedaly22/VoiceTut-TTS",
    "device": "cuda",
    "speaker": "Sayed",
    "steps": 64,
    "guidance": 2.5,
    "speed": 0.95,
    "diacritics": True,
    "postprocess": True,
    "lufs": -14,
    "multiband": "voice",
    "fmt": "wav",
    "target_sr": 48000,
    "mp3_bitrate": 320,
}


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ── الإعدادات ────────────────────────────────────────────────────────────
def load_settings() -> dict:
    """الإعدادات المخزّنة مدموجة على الافتراضيات."""
    settings = dict(DEFAULT_SETTINGS)
    settings.update(_read_json(SETTINGS_PATH))
    return settings


def save_settings(settings: dict) -> None:
    merged = dict(DEFAULT_SETTINGS)
    merged.update({k: v for k, v in settings.items() if v is not None})
    _write_json(SETTINGS_PATH, merged)


# ── قاموس النطق ──────────────────────────────────────────────────────────
def load_lexicon() -> dict[str, str]:
    return {
        str(k): str(v)
        for k, v in _read_json(LEXICON_PATH).items()
        if str(k).strip() and str(v).strip()
    }


def save_lexicon(mapping: dict[str, str]) -> dict[str, str]:
    clean = {
        str(k).strip(): str(v).strip()
        for k, v in (mapping or {}).items()
        if str(k).strip() and str(v).strip()
    }
    _write_json(LEXICON_PATH, clean)
    return clean


def lexicon_rows() -> list[list[str]]:
    """القاموس في صورة صفوف لجدول الواجهة."""
    return [[k, v] for k, v in load_lexicon().items()]


def rows_to_lexicon(rows: Optional[list]) -> dict[str, str]:
    """يحوّل صفوف الجدول لقاموس، ويتجاهل الصفوف الفاضية."""
    out: dict[str, str] = {}
    for row in rows or []:
        if row is None:
            continue
        cells = list(row)
        key = str(cells[0]).strip() if len(cells) > 0 and cells[0] is not None else ""
        val = str(cells[1]).strip() if len(cells) > 1 and cells[1] is not None else ""
        if key and val:
            out[key] = val
    return out
