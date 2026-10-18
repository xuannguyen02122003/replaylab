# ReplayLab collector (FastAPI) image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REPLAYLAB_DATABASE_URL=sqlite:////data/replaylab.db

WORKDIR /app

# Install dependencies first so this layer is cached when only code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tracer ./tracer
COPY examples ./examples

# Run as a normal user, not root. /data holds the SQLite file (a Docker volume).
RUN useradd --create-home --uid 1000 replaylab && mkdir /data && chown replaylab /data
USER replaylab

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
