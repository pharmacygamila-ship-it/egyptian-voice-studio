# 🚀 التشغيل على GPU سحابي

الهدف: تشغيل `VoiceTut-TTS` على كارت NVIDIA مستأجر (RunPod / Vast.ai)
بنفس الموديل المفتوح، وجهازك المحلي يبعت الشغل للسيرفر ده.

```
جهازك (ضعيف)  ──HTTP──►  سيرفر GPU سحابي
TTS_ENGINE=server        TTS_ENGINE=local
```

الموديل محتاج ~**6–8GB VRAM**، فكارت 16GB (RTX 4090 / A40 / L4 / A5000) كفاية ورخيص.

---

## الطريقة أ: RunPod (الأسهل)

1. **اعمل حساب** على [runpod.io](https://runpod.io) وأضف رصيد (يبدأ من ~$10).
2. **Deploy → GPU Pod**:
   - GPU: **RTX 4090** أو **L4** أو **A40**.
   - Template: **RunPod PyTorch 2.x** (CUDA 12.x).
   - Disk: 30GB على الأقل (الموديلات بتاخد مكان).
   - عرّض منفذ HTTP: **8000**.
3. **افتح Terminal** (Web Terminal) وارفع الكود:

   ```bash
   cd /workspace
   git clone <رابط-ريبو-المشروع> app   # أو ارفع الملفات من واجهة RunPod
   cd app
   bash deploy/setup_gpu.sh
   TTS_SERVER_TOKEN="$(openssl rand -hex 24)" bash deploy/run_server.sh
   ```
   اكتب التوكن اللي ظهر، هتحتاجه من جهازك.

4. **خُد الرابط**: من RunPod → Connect → **HTTP Service Port 8000**
   هيبقى شكله: `https://xxxxx-8000.proxy.runpod.net`

5. **اختبر من جهازك** (PowerShell):

   ```powershell
   .\.venv\Scripts\python.exe poc_generate.py `
     --server https://xxxxx-8000.proxy.runpod.net `
     --token   التوكن-بتاعك `
     --speaker Sayed `
     --text-file data\scripts\ad1.txt `
     --out data\outputs\ad1_cloud.wav
   ```

> 💡 نصيحة توفير: خلي `HF_HOME=/workspace/models` عشان الأوزان تتحمّل مرة واحدة
> وتفضل موجودة لو عملت Pod جديد بنفس الـ volume.

---

## الطريقة ب: Vast.ai

1. ابحث عن عرض فيه كارت **RTX 4090 / A40 / L4** وصورة **PyTorch (CUDA 12.x)**.
2. في «On-start script» أو عبر Terminal:

   ```bash
   cd /workspace && git clone <رابط-الريبو> app && cd app
   bash deploy/setup_gpu.sh
   TTS_SERVER_TOKEN="$(openssl rand -hex 24)" bash deploy/run_server.sh
   ```
3. افتح البورت **8000** من إعدادات النسخة، وخُد رابط الـ IP العام.

---

## الطريقة ج: Docker (لو عايز صورة جاهزة)

```bash
docker build -t egyptian-tts:latest .
docker run --gpus all -p 8000:8000 \
  -e TTS_SERVER_TOKEN=سرّك \
  -v tts-models:/models \
  egyptian-tts:latest
```

أو:

```bash
cd deploy && TTS_SERVER_TOKEN=سرّك docker compose up --build
```

---

## ربط التطبيق المحلي بالسيرفر

عيّن المتغيّرات على جهازك قبل ما تشغّل `backend/main.py` أو `poc_generate.py`:

```powershell
$env:TTS_ENGINE = "server"
$env:TTS_SERVER_URL = "https://xxxxx-8000.proxy.runpod.net"
$env:TTS_SERVER_TOKEN = "التوكن"
```

كده الواجهة والـ API بتاعك بيشتغلوا محلياً، بس التوليد بيحصل على الـ GPU.

---

## 🔐 أمان (مهم للتجاري)

- لازم تحدد `TTS_SERVER_TOKEN` — من غيره أي حد يعرف الرابط يقدر يستخدم الـ GPU بتاعك.
- RunPod بيوفّر HTTPS على الرابط العام تلقائياً.
- خزّن التوكن في `.env` (متسجّل في `.dockerignore`) مش في الكود.

---

## تقديرات التكلفة

| البند | القيمة |
| --- | --- |
| RunPod RTX 4090 | ~$0.34–0.69/ساعة |
| RunPod L4 | ~$0.20–0.44/ساعة |
| إعلان 30 ثانية | ثوانٍ قليلة على GPU (RTF ~1× أو أقل) |
| تكلفة إنتاج إعلان | تكسر جزء من السنت |

> وقت ما مش بتشتغل **اقفل الـ Pod** — بتدفع بالساعة بس.
