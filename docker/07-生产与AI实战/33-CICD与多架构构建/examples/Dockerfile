# syntax=docker/dockerfile:1
# 一个文件三个阶段：base 共用，api/worker 各自产出
FROM alpine:3.20 AS base

ARG APP_VERSION=dev
LABEL org.opencontainers.image.version=$APP_VERSION
LABEL org.opencontainers.image.source=https://example.com/repo

RUN mkdir -p /out && echo "exported by ${APP_VERSION}" > /out/hello.txt

WORKDIR /app
CMD ["sh", "-c", "cat /app/role 2>/dev/null || echo base"]

FROM base AS api
RUN echo api > /app/role

FROM base AS worker
RUN echo worker > /app/role
