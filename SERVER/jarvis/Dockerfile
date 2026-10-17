FROM python:3.11-slim

# ── System deps for JARVIS Voice Server ──────────────────────────────────────
# edge-tts: no extra OS deps (pure Python async)
# faster-whisper: requires libsndfile for audio (optional, graceful fallback if absent)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Copy SERVER package (JARVIS + integration gateway) ──────────────────────
COPY SERVER/ /app/SERVER/
COPY portal/ai_config.json /app/ai_config.json

# ── Install Python deps ───────────────────────────────────────────────────────
# Core: stdlib http.server (zero dep for server itself)
# LLM providers: Google Generative AI + OpenAI + Anthropic + Groq
# TTS: edge-tts (Microsoft EdgeTTS, free neural TTS)
# STT: optional faster-whisper (graceful fallback to API if absent)
RUN pip install --no-cache-dir \
    google-generativeai \
    google-genai \
    openai \
    anthropic \
    groq \
    mistralai \
    "edge-tts>=7.3.1" \
    aiofiles \
    aiohttp \
    httpx \
    redis \
    psycopg2-binary \
    nats-py \
    websockets \
    asyncio \
    python-dotenv \
    && pip install --no-cache-dir faster-whisper || echo "[WARN] faster-whisper not installed — STT will use API fallback"

# ── Environment defaults ──────────────────────────────────────────────────────
ENV JARVIS_VOICE_API_HOST=0.0.0.0
ENV JARVIS_VOICE_API_PORT=8089
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8089

# ── Health probe ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8089/jarvis/health', timeout=5)" || exit 1

# ── Entrypoint: Start JARVIS Voice API Server ─────────────────────────────────
CMD ["python3", "-u", "-m", "SERVER.jarvis.api.jarvis_voice_server"]
