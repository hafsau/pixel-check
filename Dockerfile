# PixelCheck live API (FastAPI) — the image Render runs. Models run on Nebius Token Factory and renders in Token
# Factory Sandboxes; this container orchestrates: perception (Tesseract OCR + measurement), the fluid compiler,
# the repair agent's JSX tool (node + @babel/parser), capture scripts uploaded to the sandbox. Runs on Render free:
# 512 MB, files wiped on sleep — state that must survive (caps, spend) lives in a gist (orchestrator/state.py).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# the JSX tool resolves @babel/parser from sandbox/package.json (orchestrator/jsx_tool.mjs)
COPY sandbox/package.json /app/sandbox/package.json
RUN cd /app/sandbox && npm install --no-save --no-audit --no-fund --omit=dev @babel/parser@7.28.4

COPY sandbox/fonts /app/sandbox/fonts
COPY orchestrator /app/orchestrator
COPY tools /app/tools

ENV LIVE_DIR=/tmp/pixelcheck/live LEDGER_PATH=/tmp/pixelcheck/spend.jsonl VISION_CACHE_DIR=/tmp/pixelcheck/cache/vision \
    PYTHONUNBUFFERED=1 JOB_SLOTS=1
RUN cd /app && python -m orchestrator.preflight --static

CMD ["sh", "-c", "cd /app && python -m orchestrator.preflight; exec uvicorn orchestrator.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
