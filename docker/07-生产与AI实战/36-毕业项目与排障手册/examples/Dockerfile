# 毕业项目镜像：版本通过构建参数注入，便于演练发布与回滚
FROM python:3.12-slim

ARG APP_VERSION=v1
ENV APP_VERSION=${APP_VERSION} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

LABEL org.opencontainers.image.version=${APP_VERSION}

WORKDIR /app
COPY app.py .

RUN useradd --uid 10001 --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=3s --timeout=2s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"

CMD ["python", "app.py"]
