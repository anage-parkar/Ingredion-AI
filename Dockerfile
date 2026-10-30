# syntax=docker/dockerfile:1
# Ingredion Agentic AI Factory — one image for both Cloud Run services:
#   api     (default command)  uvicorn app.main:app
#   worker  python -m app.worker --agent order-intake | --agent prebill
# Small, non-root, pinned base; the SOW 5.4 scans (SAST, secrets, dependencies, image) run on this image in Cloud Build.
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY requirements.txt requirements-gcp.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt -r requirements-gcp.txt

FROM python:3.11-slim AS runtime
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONUTF8=1 PORT=8000
WORKDIR /app
COPY app ./app
COPY factory ./factory
COPY order_intake_agent ./order_intake_agent
COPY prebill_agent ./prebill_agent
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health', timeout=4).status==200 else 1)"
# api by default; the worker service overrides the command with: python -m app.worker --agent <order-intake|prebill>
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1"]
