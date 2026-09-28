# Chat UI container: FastAPI app (src/app.py) serving web/index.html and POST /chat.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

COPY src/ ./src/
COPY web/ ./web/

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Shell form so ${PORT} is expanded by Container Apps at runtime.
CMD ["sh", "-c", "exec uvicorn src.app:app --host 0.0.0.0 --port ${PORT}"]
