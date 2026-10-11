"""يحفظ توكن Hugging Face في مكانه القياسي (يخلي كوتة الـ Space أعلى).

بيحفظه في `~/.cache/huggingface/token` — المكان اللي بيقراه
`huggingface_hub` والمحرك الأونلاين بتاعنا تلقائيًا. التوكن **مش** بيتكتب
جوه الريبو ولا بيتعمل له commit.

الاستخدام:
    .venv\\Scripts\\python.exe set_hf_token.py                 # يسألك تلزق التوكن (مخفي)
    .venv\\Scripts\\python.exe set_hf_token.py --check         # يتأكد إنه شغّال
    .venv\\Scripts\\python.exe set_hf_token.py --token hf_xxx  # بدون سؤال

تجيب التوكن من: https://huggingface.co/settings/tokens  (النوع: Read)
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

TOKEN_PATH = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "token")


def save_token(token: str) -> str:
    """يكتب التوكن في مكان HF القياسي (صلاحيات 600 على الأنظمة اللي بتدعمها)."""
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as fh:
        fh.write(token.strip())
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass
    return TOKEN_PATH


def mask(token: str) -> str:
    token = token.strip()
    if len(token) <= 10:
        return "***"
    return f"{token[:6]}...{token[-4:]}"


def check_token(token: str) -> tuple[bool, str]:
    """يتأكد إن التوكن صالح عبر whoami-v2."""
    import requests

    try:
        r = requests.get(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {token.strip()}"},
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"مش قادر أوصل لـ Hugging Face: {exc}"
    if r.status_code != 200:
        return False, f"التوكن مرفوض (HTTP {r.status_code})"
    try:
        name = r.json().get("name", "?")
    except Exception:  # noqa: BLE001
        name = "?"
    return True, f"التوكن سليم — مسجّل باسم: {name}"


def read_existing() -> str | None:
    try:
        with open(TOKEN_PATH, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="حفظ توكن Hugging Face")
    ap.add_argument("--token", help="التوكن مباشرة (hf_...)")
    ap.add_argument("--check", action="store_true", help="يتأكد من التوكن المحفوظ بس")
    args = ap.parse_args()

    if args.check and not args.token:
        existing = read_existing()
        if not existing:
            print("مفيش توكن محفوظ. شغّل السكربت من غير --check الأول.")
            return 1
        ok, msg = check_token(existing)
        print(f"[{'OK' if ok else 'FAIL'}] {mask(existing)} — {msg}")
        return 0 if ok else 1

    token = args.token or getpass.getpass("الصق توكن Hugging Face (hf_...) ثم Enter: ")
    token = (token or "").strip()
    if not token:
        print("مفيش توكن — تم الإلغاء.")
        return 1

    path = save_token(token)
    print(f"[OK] اتخزن في: {path}")
    print(f"     {mask(token)}")

    ok, msg = check_token(token)
    print(f"[{'OK' if ok else 'FAIL'}] {msg}")
    if ok:
        print("\nتقدر دلوقتي تشغّل التوليد عادي (المحرك هيلاقي التوكن لوحده).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
