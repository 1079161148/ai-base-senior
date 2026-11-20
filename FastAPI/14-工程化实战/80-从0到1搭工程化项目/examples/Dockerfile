# 单阶段构建：示例项目依赖少，多阶段收益不明显
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /srv

# 先装依赖再拷代码：改业务代码不会让依赖层缓存失效
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
RUN uv sync --no-dev

COPY app ./app
COPY scripts ./scripts

# 非 root 运行
RUN useradd --create-home appuser && chown -R appuser /srv
USER appuser

EXPOSE 8000

# 探针打 /healthz（不查库，库抖动不该引发重启）
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"

# 多 worker + 反向代理头；镜像里禁止热重载
CMD ["uv", "run", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--proxy-headers"]