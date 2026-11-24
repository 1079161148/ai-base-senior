# 22 生产级 Dockerfile · 完整版

## 0. 怎么用

跑 12/12。本章量化验证非 root、健康检查、只读根、信号处理是否真的生效。

## 1. 概念

"能跑"和"能进生产"是两回事。生产镜像要能：被编排系统探活、收到信号后优雅退出、被攻破后损失最小、版本可复现。

## 2. 机制

```text
USER appuser       → 容器主进程以 uid 10001 运行
HEALTHCHECK        → dockerd 每 interval 执行一次 CMD，结果写入 State.Health
STOPSIGNAL SIGTERM → docker stop 发送该信号而非默认
--read-only        → 根文件系统以只读方式挂载，仅 tmpfs 可写
```

## 3. 逐个拆解（本机实测）

| 项 | 实测 |
| --- | --- |
| `Config.User` | `appuser` |
| `id -u`（容器内） | `10001` |
| `Config.Healthcheck.Test` | `["CMD-SHELL", "python -c ..."]` |
| `State.Health.Status` | `healthy` |
| `Config.StopSignal` | `SIGTERM` |
| OCI 标签 | title/vendor/version |
| `--read-only` 写 `/app` | `Read-only file system` |
| `docker stop` | 日志 `graceful shutdown` |

## 4. 边界条件

- `USER` 只改运行身份，不改文件属主；不 `chown` 会写不进工作目录。
- 健康检查的 `start-period` 内的失败不计入重试，要给应用留启动时间。
- `--read-only` 下很多应用会崩（要写 pid、日志、缓存），需挂 tmpfs 或配到 stdout。
- `PYTHONUNBUFFERED=1` 不加会导致日志延迟输出，排障困难。
- 固定小版本仍可能被覆盖（tag 可变），最严格用 `image@sha256:` digest。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 默认 root 运行 | 逃逸风险高 | `USER` + `chown` | 实测 |
| 健康检查指向 404 | 永远 unhealthy | 检查 200 端点 | 实测 |
| shell 形式 CMD | 信号丢失 | exec 形式 | 第 18 章 |
| 只读根不挂 tmpfs | 启动崩溃 | `--tmpfs /tmp` | 实测 |
| 不设 STOPSIGNAL | 用默认 TERM，某些栈需 SIGINT | 显式声明 | 官方 |
| 用 latest | 版本漂移 | 固定 tag/digest | 第 06 章 |
| 不设 LANG | 中文乱码 | `C.UTF-8` | 实测 |
| 不开 unbuffered | 日志延迟 | `PYTHONUNBUFFERED=1` | 实测 |
| 不打 OCI 标签 | 无法追溯 | `org.opencontainers.image.*` | 最佳实践 |
| 跳过验收 | 生产隐患 | 12/12 再走 | 实测 |

## 6. 最佳实践

模板固定为：多阶段 + 固定版本 + 非 root + HEALTHCHECK + STOPSIGNAL + 只读根 + 日志走 stdout；上线前用 `docker scout`/`trivy` 扫漏洞（第 30 章）。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Dockerfile best practices |
| `[r3]` | 实测 | 12/12，只读根与优雅退出已实证 |

## 8. 毕业自查

- [ ] 12/12 通过
- [ ] 能独立写一份生产级 Dockerfile

## 9. 下一章

M04 完成。第 23 章进入 M05，学镜像仓库与推送。
