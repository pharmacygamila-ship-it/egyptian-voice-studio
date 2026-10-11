# صورة GPU لتشغيل VoiceTut-TTS + الـ API
# الأساس فيها PyTorch + CUDA جاهزين
FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    TTS_ENGINE=local \
    TTS_OUTPUT_DIR=/outputs

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# مكتبات الـ API (خفيفة)
RUN pip install --no-cache-dir \
        fastapi "uvicorn[standard]" python-multipart soundfile numpy requests

# محرك الصوت المصري
RUN pip install --no-cache-dir git+https://github.com/k2-fsa/OmniVoice.git \
    && pip install --no-cache-dir voicetut-tts

COPY backend ./backend
COPY requirements.txt ./requirements.txt

RUN mkdir -p /models /outputs

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
