# 🎙️ استوديو الصوت المصري — عامية مصرية

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pharmacygamila-ship-it/egyptian-voice-studio/blob/main/deploy/colab_model_server.ipynb)

تطبيق لإنتاج تعليق صوتي (Voice Over) للإعلانات بالعامية المصرية + استنساخ صوت العميل،
مبني على **[VoiceTut-TTS](https://huggingface.co/mohammedaly22/VoiceTut-TTS)**
(مصري أصلي + code-switching عربي↔إنجليزي + 17 صوت + استنساخ، رخصة Apache-2.0 → تجاري مسموح).

> ⭐ **المسار الرئيسي**: الموديل (GPU) على **كولاب**، والتطبيق عندك يتصل بيه **بمفتاح** —
> يعني كل عمليات الموديل **سحابية**. الدليل: [`COLAB.md`](COLAB.md) · الخطة: [`PLAN.md`](PLAN.md).
> (وفيه بديل: تشغيل التطبيق كله على كولاب — نفس الدليل.)

---

## ⚡ الحالة الحالية

- ✅ **الموديل على Colab (سحابي)**: سيرفر الموديل يشتغل على GPU T4 مجاني، والتطبيق يتصل بيه **بمفتاح** (`X-Auth-Token`).
- ✅ **تطبيق واحد يتحكم في كل حاجة**: توليد · استنساخ · دفعي · فحص نطق · قاموس نطق · إعدادات.
- ✅ **تطبيع مصري متقدّم** (من حزمة الموديل، بيشتغل CPU): `15` → **خَمَسْتَاشَر**، `3:30` → **تَلَاتَة و نُصّ**، `75$` → **خمسة وسبعين دولار**.
- ✅ **منع التطبيع المزدوج** (التطبيع مرتين بيشيل التشكيل).
- ✅ **فاحص النطق (ASR)**: يقارن الناتج بالنص **بالحرف** (`backend/qa/asr_check.py`).
- ✅ **معالجة بجودة بث**: EBU R128 + de-esser + multi-band + limiter + MP3 بدون ffmpeg.
- ✅ **قاموس نطق + إعدادات** بيتحكموا من التطبيق ويتحفظوا تلقائيًا.
- ✅ كل الاختبارات ناجحة: `tests/run_all.py` (selfcheck + text + audio + finetune + gradio + qa + http).
- 🟡 **فاين-تيون لموديل خاص** (اختياري): `finetune/` — محتاج GPU + تسجيل صوت العميل.

---

## 🗂️ بنية المشروع

```
اعلانات 2/
├─ COLAB.md                    دليل التشغيل الكامل على Colab (المسار الرئيسي)
├─ PLAN.md                     الخطة الكاملة
├─ README.md                   الدليل ده
├─ LICENSE                     رخصة Apache-2.0
├─ publish.ps1                 نشر الريبو على GitHub بأمر واحد
├─ Dockerfile                  صورة GPU جاهزة
├─ requirements.txt            مكتبات محلية (خفيفة)
├─ requirements-gpu.txt        مكتبات GPU
├─ poc_generate.py             سطر أوامر للتوليد السريع
├─ batch_generate.py           توليد دفعي لكل الإعلانات
├─ set_hf_token.py             حفظ توكن Hugging Face (كوتة أعلى للـ Space)
├─ .env.example                مثال إعدادات
├─ frontend/
│   ├─ index.html              واجهة الويب (RTL)
│   └─ app_gradio.py           التطبيق (مركز تحكم كامل: توليد/استنساخ/دفعي/فحص/قاموس/إعدادات)
├─ backend/
│   ├─ main.py                 FastAPI (/health /voices /tts /clone) + حماية توكن
│   ├─ store.py                حفظ الإعدادات + قاموس النطق (JSON محلي)
│   ├─ engine/
│   │   ├─ base.py             الواجهة المشتركة
│   │   ├─ factory.py          اختيار المحرك (TTS_ENGINE)
│   │   ├─ remote_voicetut.py  محرك أونلاين (الـ Space)
│   │   ├─ server_client.py    عميل سيرفر GPU بتاعنا
│   │   └─ local_voicetut.py   محرك محلي/GPU
│   ├─ qa/
│   │   └─ asr_check.py        فاحص النطق (ASR + مقارنة بالحرف)
│   ├─ text/
│   │   ├─ normalize.py        تطبيع النص (normalize_for_tts = المدخل الرئيسي)
│   │   ├─ voicetut_norm.py    طبقة تطبيع الموديل (أرقام/تواريخ/تشكيل) — CPU
│   │   ├─ numbers.py          الأرقام → كلام مصري (خمسين / ألفين…)
│   │   ├─ lexicon.py          نطق الأجنبي + الوحدات (واتساب / كيلوجرام)
│   │   └─ diacritics.py       تشكيل كلمات ملتبسة (اختياري)
│   └─ audio/
│       ├─ postprocess.py      معالجة صوت إعلانية + ضغط متعدد النطاقات
│       └─ export.py           تصدير WAV/MP3 (بدون ffmpeg)
├─ deploy/
│   ├─ README.md               خطوات RunPod / Vast.ai / Docker / Colab / Modal
│   ├─ setup_gpu.sh            تجهيز بيئة GPU
│   ├─ run_server.sh           تشغيل السيرفر
│   ├─ docker-compose.yml
│   ├─ colab_model_server.ipynb  سيرفر الموديل على Colab (رابط عام + مفتاح) ⭐
│   ├─ colab_free_gpu.ipynb    التطبيق كله على Colab (محرك local)
│   └─ modal_app.py            نشر على Modal (رصيد مجاني)
├─ finetune/
│   ├─ README.md               مسار «نفس الأداء» (Zero-shot + Fine-tune)
│   ├─ RECORDING.md            دليل تسجيل صوت العميل
│   ├─ prepare_dataset.py      تجهيز داتاسِت التدريب
│   └─ train_lora.py           سكربت التدريب (LoRA)
├─ tests/
│   ├─ selfcheck.py            فحص المكونات
│   ├─ test_text.py            فحص طبقة النص المصري (أرقام/نطق/تنضيف)
│   ├─ test_audio.py           فحص المعالجة الصوتية (LUFS/de-esser/high-pass)
│   ├─ test_finetune.py        فحص تجهيز داتاسِت fine-tune
│   ├─ test_gradio.py          فحص التطبيق (توليد/دفعي/قاموس/إعدادات)
│   ├─ test_qa.py              فحص فاحص النطق (مقارنة الحروف)
│   ├─ check_http.py           فحص السيرفر والعميل
│   └─ run_all.py              يشغّل كل الاختبارات مرة واحدة
├─ .github/workflows/tests.yml CI على GitHub
└─ data/
    ├─ scripts/                نصوص الإعلانات
    └─ outputs/                الأصوات المُولّدة
```

---

## 🚀 التشغيل

### ⭐ المسار الرئيسي: موديل على كولاب + تطبيق بمفتاح
**1) شغّل سيرفر الموديل على كولاب (GPU):**
[deploy/colab_model_server.ipynb](https://colab.research.google.com/github/pharmacygamila-ship-it/egyptian-voice-studio/blob/main/deploy/colab_model_server.ipynb)
- `Runtime` → `Change runtime type` → **T4 GPU** → `Save`
- شغّل الخلايا → هيطلعلك **🔗 رابط السيرفر** + **🔑 المفتاح**

**2) شغّل التطبيق عندك واربطه بالمفتاح:**
```powershell
.\.venv\Scripts\python.exe frontend\app_gradio.py            # http://127.0.0.1:7860
```
تاب **⚙️ الإعدادات** → نوع المحرك = `server` → الصق **الرابط** و**المفتاح** → **🔌 اختبار الاتصال** → **✅ تطبيق وتشغيل**.

> الخطوات بالتفصيل في **[`COLAB.md`](COLAB.md)**. كل عمليات الموديل (توليد/استنساخ) بتحصل **سحابيًا** على كولاب.

### 🔁 بديل: التطبيق كله على كولاب (من غير مفتاح)
[deploy/colab_free_gpu.ipynb](https://colab.research.google.com/github/pharmacygamila-ship-it/egyptian-voice-studio/blob/main/deploy/colab_free_gpu.ipynb) → شغّل الخلايا → رابط عام `https://xxxx.gradio.live` للتطبيق الكامل (محرك `local`).

| التاب | الوظيفة |
| --- | --- |
| 🔊 **توليد** | نص + صوت + **معاينة النطق** بعد التطبيع |
| 🧬 **استنساخ صوت** | مقطع مرجعي 10–30 ثانية (بموافقة صاحب الصوت) |
| 📦 **دفعي** | ملفات `.txt` → ملف zip (سمّ الملف `اسم__الصوت.txt`) |
| 🔎 **فاحص النطق** | ASR + مقارنة بالنص **بالحرف** (أحرف ناقصة/زيادة) |
| 📖 **قاموس النطق** | كلمات/براندات بنطقها المخصوص |
| ⚙️ **الإعدادات** | نوع المحرك + رابط السيرفر + المفتاح + الموديل — **تُحفظ تلقائيًا** |

### 🔌 سيرفر الموديل (الـ API اللي كولاب بيشغّله)
> ده اللي بيشتغل على كولاب في المسار الرئيسي. تشغيله محليًا (لو عندك GPU):
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```
- `GET /health` · `GET /voices` · `POST /tts` · `POST /clone` · `POST /warmup`
- الحماية: لو `TTS_SERVER_TOKEN` متعيّن، لازم كل الطلبات تبعث هيدر `X-Auth-Token`.

### ⌨️ سطر أوامر (اختياري)
```powershell
.\.venv\Scripts\python.exe poc_generate.py --speaker Sayed --text "أهلاً بيك في تطبيقنا الجديد"
.\.venv\Scripts\python.exe batch_generate.py --speaker Sayed --multiband voice --mp3 --zip ads.zip
.\.venv\Scripts\python.exe -m backend.qa.asr_check data\outputs\ad1.wav "النص الأصلي المتوقع"
```

> 💡 **نوع المحرك** (من تاب الإعدادات أو `TTS_ENGINE`): `server` (سيرفر الموديل على كولاب) · `remote` (Space جاهز) · `local` (GPU على نفس الجهاز).

---

## 🎧 الأصوات الجاهزة (17)

| ذكور | إناث |
| --- | --- |
| Abdelrahman, Abdullah, Kamal, Hossam, Mohamed, Omar, **Sayed**, Zaki, Aly, Essam, Ahmed | Asmaa, Esraa, Hanan, Sarah, **Yasmin**, Omnia |

> «Sayed» (شبابي/معبّر) و«Yasmin» (شبابي/مشرق) مناسبين جداً للإعلانات.

---

## ⚙️ المحركات

| المحرك | متى تستخدمه | المتطلب |
| --- | --- | --- |
| `server` ⭐ | **المسار الرئيسي** — الموديل على كولاب والتطبيق بمفتاح | رابط + مفتاح من `deploy/colab_model_server.ipynb` |
| `remote` | تجارب سريعة، من غير كارت | إنترنت + كوتة Space |
| `local` | تشغيل على كارت NVIDIA عندك (أو جوّه كولاب) | GPU (8GB+) |

التبديل عن طريق متغيّر البيئة `TTS_ENGINE`:

```powershell
# الموديل على كولاب (المسار الرئيسي)
$env:TTS_ENGINE = "server"
$env:TTS_SERVER_URL = "https://xxxx.trycloudflare.com"   # الرابط من نوتبوك كولاب
$env:TTS_SERVER_TOKEN = "vs_..."                          # المفتاح من نوتبوك كولاب
```

---

## ☁️ التشغيل على GPU سحابي

الموديل محتاج ~6–8GB VRAM. أسهل طريق:
1. اعمل GPU Pod على **RunPod** (RTX 4090 / L4 / A40).
2. `bash deploy/setup_gpu.sh` ثم `bash deploy/run_server.sh`.
3. من جهازك: `TTS_ENGINE=server` + الرابط + التوكن.

**التفاصيل الكاملة في [`deploy/README.md`](deploy/README.md)** (RunPod + Vast.ai + Docker).

### 🆓 مجاناً (بدون بطاقة)
- **Colab (T4 مجاني)** ⭐ — **سيرفر الموديل بمفتاح** (المسار الرئيسي) → `deploy/colab_model_server.ipynb`
  · أو التطبيق كله على كولاب → `deploy/colab_free_gpu.ipynb`
- **Modal** — $30/شهر رصيد لسيرفر API دائم → `deploy/modal_app.py`
- **HF Space** — تجارب سريعة (كوتة ZeroGPU محدودة) → المحرك `remote`

### 💻 نبني نماذجنا بنفسنا (مش محتاجين Space)
عشان نبقى مستقلين تمامًا عن أي سيرفر عام:
```bash
# على أي جهاز فيه GPU (أو Colab):
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install git+https://github.com/k2-fsa/OmniVoice.git
pip install voicetut-tts

# بعدين استخدم المحرك المحلي:
TTS_ENGINE=local .venv/bin/python -m uvicorn backend.main:app --port 8000
# أو من نفس المشروع:
.venv/Scripts/python poc_generate.py --engine local --speaker Sayed --text "عرض النهاردة"
```
الموديل **2.45GB** فقط (~3GB VRAM) وApache-2.0 → تجاري. وللفاين-تيون على دومين/صوت معيّن
شوف [`finetune/README.md`](finetune/README.md) (نفس مسار OmniVoice).

### 🔁 توليد دفعي
```powershell
# محلياً (عبر السيرفر) أو على Colab/Kaggle (محرك محلي)
.\.venv\Scripts\python.exe batch_generate.py --speaker Sayed --zip ads.zip
```
سمّي الملف `ad2__Yasmin.txt` لو عايز صوت مختلف لكل إعلان.

### كوتة الـ Space المجاني
النسخة المجانية (ZeroGPU) بكوتة محدودة وممكن ترفض الطلبات (حصل معانا). حلول:
- تشغيل محرك محلي على GPU (**مستحسن**) — Colab مجاناً أو GPU مستأجر → `TTS_ENGINE=local`.
- تعيين `HF_TOKEN` (توكن HuggingFace) → كوتة أعلى على الـ Space.
- استئجار GPU سحابي (RunPod / Vast.ai) وتشغيل `LocalVoiceTutEngine`.

---

## 🗣️ طبقة النص المصري

فيه **طبقتين** للتطبيع:

**1) الطبقة الحديثة `normalize_for_tts`** (الافتراضية للـ API/CLI/الواجهة): مبنية على حزمة
`voicetut-tts` — نفس طبقة التطبيع اللي الموديل اتدرّب عليها، وبتشتغل **CPU-only** (من غير torch).
بتدّي نطق أدق للعامية:

| الخطوة | مثال |
| --- | --- |
| أرقام → كلام مصري مشكول | `50` → **خَمْسِين** · `15` → **خَمَسْتَاشَر** |
| أوقات بالعامية | `3:30` → **تَلَاتَة و نُصّ** · `7:45` → **تَمَانْيَه الا رُبع** |
| عملات/نِسب | `75$` → **خمسة وسبعين دولار** · `25%` → **خَمْسَه وعِشْرين في المية** |
| تليفون ميل/روابط | `01147450629` → **زيرو حْدَاشَر…** · `a.b@gmail.com` → **a dot b at gmail dot com** |
| أسماء إنجليزية | `Ahmed` → **أحمد** |
| code-switching | `عندي meeting بكرة` → الإنجليزي بيفضل زي ما هو (الموديل بينطقه صح) |

**2) الطبقة المدمجة `normalize_egyptian`** (fallback لما الحزمة مش متثبّتة).

التحكم (نفس الواجهة):
```python
from backend.text.normalize import normalize_for_tts
normalize_for_tts("خصم 50%")                    # → "خصم خَمْسِين في المية"
normalize_for_tts("خصم 50", diacritics=False)   # الأرقام بتفضل مشكولة للضرورة
normalize_for_tts("...", modern=False)          # يجبر الطبقة المدمجة
normalize_for_tts("...", lexicon={"Nescafe": "نِسْكافِيه"})  # نطق مخصوص
```

> ⚠️ مهم: بنمرّر `normalize=False` للمحرك بعد ما نطبّع، لأن **تطبيع الموديل مرتين بيشيل التشكيل**.

**تعديل القواميس:** `backend/text/lexicon.py` (كلمات أجنبية/وحدات) و `backend/text/numbers.py` (صيغ الأرقام) و `backend/text/diacritics.py` (التشكيل).

---

## 🔎 فاحص النطق (ASR) — نتأكد إن مفيش أحرف ناقصة/زيادة

بعد التوليد، نقدر نسمّع الناتج ونقارنه بالنص المتوقّع **موضوعيًا**:

```bash
.venv\Scripts\python.exe -m backend.qa.asr_check out.wav "وريحة تجنن"
```

بيطلّع نسبة تطابق + كل خطأ بالحرف:
```
نسبة التطابق: 88.0%
المتوقّع : ... وريحه تجنن ...
المسموع : ... وريحه جنن ...
⚠️ الأخطاء:
  - خطأ: «تجنن» → «جنن»  [-ت]
```
> بيستخدم `faster-whisper` محلي (CPU). ملاحظة: الـ ASR بيصحّح النطق المصري للمعيارية (مثلاً
> «قهوة» بنطقها المصري **"أَهْوَه"** = ق مصري = همزة)، فنتايج القرب من المعيارية تعتبر **مقبولة**.
> للتحقق الأدق للعامية استخدم نموذج **[QwenCleo-ASR](https://github.com/MohammedAly22/qwencleo-asr)** المصري.

---

## 🎚️ معالجة الصوت (Mastering) — جودة بث

كل صوت بيخرج من الموديل بيمر على `backend/audio/postprocess.py`:

| الخطوة | الفايدة |
| --- | --- |
| تشذيب السكوت | يشيل الفراغات من الأول والآخر |
| High-pass (80Hz، رتبة 4) | شيل الزمزمة/الدبدبة → صوت أنضف |
| **De-esser** (5–9kHz) | يهدّي حروف السين/الشين الحادّة |
| **Multiband** (اختياري) | ضغط/EQ ٣ نطاقات → صوت متوازن وواضح (إحساس «إعلاني») |
| **EBU R128** | جهارة موحّدة **-14 LUFS** (معيار يوتيوب/سبوتيفاي/البث) |
| **Limiter** (look-ahead) | تحديد القمم عند ≤ **-1 dBTP** بدون ما نخسر جهارة المقطع |
| Fade + Resample | دخول/خروج ناعم + تصدير 48kHz |

```python
from backend.audio.postprocess import postprocess, analyze
from backend.audio.export import export
postprocess("in.wav", "out.wav", target_lufs=-14.0, target_sr=48000, multiband="voice")
print(analyze("out.wav"))   # {"sr":48000,"seconds":..,"lufs":-14.0,"peak_dbfs":-4.6}
export("out.wav", "mp3", bitrate=192)   # → out.mp3 (بدون ffmpeg)
```

مستويات جاهزة: **-16** بودكاست · **-14** بث/إعلانات (افتراضي) · **-12** إعلان صاخب · **-9** أقصى جهارة.
متاح من الواجهة ومن الـ API (خانة `lufs`)، وكله محلي من غير أي برنامج خارجي.

**الضغط متعدد النطاقات (`multiband`):** `voice` متوازن · `warm` دافي · `punch` حماسي · `broadcast` بث/راديو.
**تصدير MP3:** عبر `lameenc` (192kbps افتراضي) — من الواجهة (صيغة الملف) أو `fmt=mp3` في الـ API أو `--mp3` في الـ CLI.

---

## 🐙 النشر على GitHub

الريبو جاهز للنشر (رخصة Apache-2.0 + CI + توحيد نهايات الأسطر).

```powershell
# 1) أنشئ ريبو فاضي على GitHub (من غير README) ← من الموقع
# 2) انشره بأمر واحد:
.\publish.ps1 -RepoUrl "https://github.com/USERNAME/REPO.git"
```

CI بيشغّل كل الاختبارات تلقائياً على كل push (`.github/workflows/tests.yml`).

---

## 📋 الخطوات الجاية

1. ✅ **عينة على GPU سحابي**: اتعملت عبر `HF_TOKEN` (كوتة أعلى) → `data/outputs/cloud_sample_Sayed.wav` (+`.mp3`).
   - **Colab/Kaggle مجاني** (للدُفعات): `deploy/colab_free_gpu.ipynb`.
   - **Modal** (`$30` رصيد مجاني): `modal run deploy/modal_app.py`.
   - **GPU مدفوع (الإنتاج)**: `deploy/setup_gpu.sh` + `deploy/run_server.sh` (شوف `deploy/README.md`).
2. ✅ قاموس البراندات/الشركات المصرية + تشكيل الكلمات الملتبسة (`backend/text/`).
3. ✅ مسار fine-tune لاستنساخ «نفس الأداء الصوتي» (`finetune/`) — يتبقى تركيب API التدريب الرسمي.
4. ✅ تصدير MP3 + ضغط/EQ متعدد النطاقات (`backend/audio/`).
5. ✅ واجهة Gradio (`frontend/app_gradio.py`) + الريبو مرفوع على GitHub.

---

## ⚖️ قانوني (مهم للتجاري)

- موافقة **مكتوبة** من صاحب أي صوت حقيقي قبل الاستنساخ.
- إفصاح إن الصوت مصطنع عند اللزوم.
- ممنوع استنساخ أصوات مشاهير/أشخاص بدون إذن، أو استخدامها في تضليل/انتحال.
