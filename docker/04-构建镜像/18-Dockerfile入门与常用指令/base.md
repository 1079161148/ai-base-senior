# 18 Dockerfile 入门与常用指令 · 完整版

## 0. 怎么用

跑 13/13。本章从零构建两个镜像，真实验证每条指令落到 `image inspect` 的哪个字段。

## 1. 概念

Dockerfile 是声明式构建脚本。`docker build` 逐条执行，每条**修改文件系统**的指令（RUN/COPY/ADD）生成一层，其余指令只改配置。

## 2. 机制

```text
docker build -t tag .
  → 读取 Dockerfile → 逐指令执行
  → 每条 RUN/COPY 提交一层（layer, 按 cache key 复用）
  → 最后生成镜像 config（Cmd/Entrypoint/Env/WorkingDir/ExposedPorts/User/Labels）
```

## 3. 指令逐个拆解（本机实测）

| 指令 | 实测落点 |
| --- | --- |
| `FROM python:3.12-slim` | 起始层 |
| `LABEL maintainer="study"` | `Config.Labels.maintainer = study` |
| `ARG APP_VERSION=1.0` | 构建期可见，不进 Config.Env |
| `ENV APP_ENV=dev` | `Config.Env` 含 `APP_ENV=dev` |
| `WORKDIR /www` | `Config.WorkingDir = /www` |
| `COPY index.html .` | 新增一层 |
| `EXPOSE 8000` | `Config.ExposedPorts = {"8000/tcp": {}}` |
| `RUN useradd -m appuser` | 新增一层 |
| `USER appuser` | `Config.User = appuser` |
| `CMD ["python","app.py"]` | `Config.Cmd = ["python","app.py"]` |
| `ENTRYPOINT ["python","app.py"]` | `Config.Entrypoint = [...]` |
| `CMD ["--port","8000"]` | 与 ENTRYPOINT 拼接执行 |

实测：`docker history` 显示 20 层；`docker run img --port 9000` 成功覆盖 CMD 并监听 9000。

## 4. 边界条件

- `ARG` 只在构建期有效，运行时读不到；需要运行时值就用 `ENV`。
- `EXPOSE` 只是文档声明，不开放端口，必须 `-p` 映射。
- exec 形式不经过 shell，`CMD ["echo","$HOME"]` 不会展开变量，需要 `sh -c`。
- shell 形式的 PID 1 是 `/bin/sh`，SIGTERM 可能传不到应用。
- `ADD` 会自动解压 tar 并从 URL 下载，副作用多，优先 `COPY`。
- 基础镜像选择：`alpine` 小但 musl 兼容性问题（本次实测 alpine 的 busybox 竟无 httpd），`slim` 基于 glibc 更兼容。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 用 shell 形式 CMD 跑服务 | stop 不优雅 | exec 形式 | 实测 |
| 依赖 EXPOSE 开放端口 | 外部访问不到 | `-p` 映射 | 第 17 章 |
| 用 ARG 传运行时配置 | 读不到 | `ENV` | 实测 |
| `ADD` 随意用 | 意外解压/覆盖 | 用 `COPY` | 官方 |
| 不加 `.dockerignore` | 上下文巨大 | 第 20 章 | 实测 |
| 默认 root 运行 | 安全风险 | `USER` | 第 22 章 |
| `CMD ["echo","$HOME"]` | 不展开变量 | `sh -c` | 实测 |
| 选 alpine 但不验证命令 | 缺 applet（httpd） | 实测或换 slim | 实测 |
| 一个 RUN 干所有事 | 缓存粒度差 | 合理拆分 | 第 19 章 |
| 跳过验收 | 指令落点不清 | 13/13 再走 | 实测 |

## 6. 最佳实践

exec 形式 + 非 root 用户 + 明确 WORKDIR + 精简基础镜像；构建上下文加 `.dockerignore`；生产用 ENTRYPOINT + CMD 组合。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Dockerfile reference |
| `[r3]` | 实测 | 13/13，含 alpine 无 httpd 的真实坑 |

## 8. 毕业自查

- [ ] 13/13 通过
- [ ] 能默写最小可用 Dockerfile

## 9. 下一章

第 19 章深入分层与构建缓存：为什么有的改动会全量重建。
