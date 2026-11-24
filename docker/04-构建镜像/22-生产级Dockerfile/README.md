# 22 生产级 Dockerfile

## 一句话结论

生产级 Dockerfile 有六条硬指标：**固定基础镜像版本、非 root 运行、声明 HEALTHCHECK、显式 STOPSIGNAL、exec 形式 CMD、不带无关文件**。再加只读根文件系统，就是一份可以进生产的最小模板。

## 最小可运行案例

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY app.py .
RUN useradd --system --uid 10001 --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=2s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/',timeout=2)" || exit 1
STOPSIGNAL SIGTERM
CMD ["python", "app.py"]
```

## 怎么跑

```powershell
cd "04-构建镜像\22-生产级Dockerfile\examples"
uv run python verify.py
```

## 本机实测

| 检查项 | 结果 |
| --- | --- |
| `USER` | `appuser` |
| 容器内 `id -u` | `10001`（真正的非 root） |
| `HEALTHCHECK` | 存在，状态最终 `healthy` |
| `STOPSIGNAL` | `SIGTERM` |
| 只读根 + `--tmpfs /tmp` | 服务正常，写 `/app` 报 `Read-only file system` |
| `docker stop` | 日志出现 `graceful shutdown` |
| OCI 标签 | `org.opencontainers.image.*` 齐全 |

## 六条硬指标

| 指标 | 为什么 | 怎么做 |
| --- | --- | --- |
| 固定版本 | 避免 `latest` 漂移 | `python:3.12-slim`，更严用 digest |
| 非 root | 降低逃逸后权限 | `useradd` + `USER` |
| HEALTHCHECK | 编排系统能判断存活 | `HEALTHCHECK CMD ...` |
| STOPSIGNAL | 正确传递终止信号 | `STOPSIGNAL SIGTERM` |
| exec 形式 CMD | PID 1 能收信号 | `CMD ["python","app.py"]` |
| 精简内容 | 减小攻击面 | 多阶段 + `.dockerignore` |

## 只读根文件系统

```bash
docker run --read-only --tmpfs /tmp --tmpfs /run myapp:1.0
```

好处：攻击者无法落地文件；代价：应用不能写任何非 tmpfs 路径，需要提前挂好可写目录。

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 容器内还是 root | 只写了 `USER` 但文件属主错 | `chown` 后再 `USER` |
| 健康检查一直 unhealthy | 检查的 URL 返回 404 | 检查端点要 200 |
| stop 要等 10 秒 | shell 形式 CMD | exec 形式 + 处理 SIGTERM |
| 只读根下服务崩溃 | 应用要写缓存/pid | 挂 tmpfs 或改配置 |
| 时区不对 | 镜像默认 UTC | 装 tzdata 或设 `TZ` |
| 中文乱码 | 缺少 locale | 设 `LANG=C.UTF-8` |
| 日志丢 | 缓冲未关 | `PYTHONUNBUFFERED=1` |

## 毕业自查

- [ ] 12/12 通过
- [ ] 能默写生产级 Dockerfile 六要素
- [ ] 知道 `--read-only` 的适用与代价
- [ ] 知道为什么健康检查端点必须返回 200
