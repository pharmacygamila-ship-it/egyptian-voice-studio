"""فحص HTTP: يشغّل السيرفر، ويتأكد إن الـ endpoints والعميل شغالين.

    .venv\\Scripts\\python.exe tests\\check_http.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PORT = 8123
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "test-secret-123"

env = os.environ.copy()
env["PYTHONUTF8"] = "1"
env["TTS_ENGINE"] = "remote"
env["TTS_SERVER_TOKEN"] = TOKEN
env["TTS_OUTPUT_DIR"] = os.path.join(ROOT, "data", "outputs")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(PORT)],
    cwd=ROOT,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

ok = True


def check(label: str, cond: bool) -> None:
    global ok
    ok = ok and cond
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")


try:
    deadline = time.time() + 30
    up = False
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=2) as r:
                if r.status == 200:
                    up = True
                    break
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    check("السيرفر قام /health = 200", up)
    if not up:
        raise SystemExit(1)

    from backend.engine.server_client import ServerVoiceTutEngine

    # /voices بدون توكن (مفتوح)
    eng = ServerVoiceTutEngine(base_url=BASE, token=TOKEN)
    speakers = eng.list_speakers()
    check("العميل قرأ الأصوات من السيرفر (17)", len(speakers) == 17)

    # /tts بدون توكن → 401
    req = urllib.request.Request(
        f"{BASE}/tts",
        data=b'{"text":"test"}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        check("حماية التوكن (/tts بدون توكن = 401)", False)
    except urllib.error.HTTPError as e:
        check("حماية التوكن (/tts بدون توكن = 401)", e.code == 401)

    print("\n==>", "السيرفر والعميل تمام ✅" if ok else "فيه فشل ❌")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:  # noqa: BLE001
        proc.kill()

raise SystemExit(0 if ok else 1)
