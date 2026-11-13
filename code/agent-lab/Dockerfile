# syntax=docker/dockerfile:1
#
# S8 · 生产镜像。
#
# 两个阶段的意义不只是"小一点"：
#   构建阶段有 uv、缓存、编译工具；运行阶段只有 .venv 和源码。
#   最终镜像里没有 pip 缓存、没有编译器，攻击面小一圈，
#   也避免"某个依赖在本地能装、线上没装成"这类问题。

# ---------- 构建阶段 ----------
FROM ghcr.io/astral-sh/uv:0.8 AS uv

FROM python:3.12-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 先只拷依赖清单：只要源码变了、依赖没变，这一层就能命中缓存
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 再拷源码并安装项目本身
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 预下载嵌入模型（BAAI/bge-small-zh-v1.5，约 100MB）。
#
# 不预下载会怎样：容器启动时 fastembed 现场去 HuggingFace 拉模型，
# 没有外网就重试三次后启动失败；有外网也要多等几十秒，
# 而且每次重建容器都重下一遍。打在镜像里，"能不能启动"就不再取决于网络。
#
# HF_ENDPOINT 走镜像站，国内构建时不会被墙。需要直连可以 --build-arg 覆盖。
ARG HF_ENDPOINT=https://hf-mirror.com
ENV HF_ENDPOINT=${HF_ENDPOINT} \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN /app/.venv/bin/python -c \
    "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-zh-v1.5'); print('embedding model cached')"

# ---------- 运行阶段 ----------
FROM python:3.12-slim AS runtime

# curl 只用于 HEALTHCHECK。用 python -c urllib 也行，
# 但容器里有个 curl 排查问题时会顺手很多。
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 非 root 运行：容器逃逸时，root 权限会被直接放大成宿主 root
RUN useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
# 嵌入模型缓存跟着镜像走，运行时不再需要下载
COPY --from=builder --chown=app:app /app/.cache /app/.cache
COPY --chown=app:app src ./src
COPY --chown=app:app pyproject.toml README.md ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed

# config.py / db.py 用 parents[4] 定位项目根，所以目录结构必须是 /app/src/agent_lab/...
# data 目录要提前建好并给写权限（SQLite、trace 文件都写这里）
RUN mkdir -p /app/data/traces && chown -R app:app /app

USER app
EXPOSE 8001

# start-period 给 25s：pgvector 连接池 + 建表需要时间，
# 太短会被编排系统判定成"启动失败"直接重启，形成循环
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8001/api/v1/health || exit 1

CMD ["python", "-m", "uvicorn", "agent_lab.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
