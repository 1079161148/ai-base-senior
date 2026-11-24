# 生产级要点：固定版本、OCI 标签、非 root、健康检查、显式信号
FROM python:3.12-slim

LABEL org.opencontainers.image.title="prod-app" \
      org.opencontainers.image.vendor="study" \
      org.opencontainers.image.version="1.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY app.py .

RUN useradd --system --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=5s --timeout=2s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=2)" || exit 1

STOPSIGNAL SIGTERM

CMD ["python", "app.py"]
