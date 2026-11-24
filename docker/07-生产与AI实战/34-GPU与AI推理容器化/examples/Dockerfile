# 镜像里只放代码，模型权重靠挂载进来
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_DIR=/models \
    CACHE_DIR=/cache

WORKDIR /app
COPY serve.py .

RUN useradd --uid 10001 --create-home appuser && mkdir -p /models /cache && chown appuser /cache
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=2s --retries=10 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"

CMD ["python", "serve.py"]
