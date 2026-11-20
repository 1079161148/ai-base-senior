# 76 部署与交付 · 完整版（base.md）

> `README.md` 给你能跑的探针与 Dockerfile；本文件把「liveness 与 readiness 为什么必须分开、SIGTERM 后发生什么、workers 怎么定、镜像怎么不把密钥带进去」拆开。学完这章，你能把一个 FastAPI 服务安全地送上生产。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0 / uvicorn 0.54（本机实测端点与配置） |
| 前置 | 第 67 章（lifespan）、第 75 章（日志） |
| 覆盖范围 | 探针、uvicorn 参数、Dockerfile、优雅退出、构建上下文 |
| 明确不覆盖 | K8s 编排细节、CI/CD 流水线、蓝绿/金丝雀 |
| 学完验收 | 能跑通 `verify.py` 16/16、能解释两个探针的差异 |

## 0. 怎么用这份文件

**依据约定**：`` `[Zn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 交付的四件事
2 机制（第 2 节）    → 探针与 SIGTERM
3 API（第 3 节）     → uvicorn 参数逐个
4 边界（第 4 节）    → workers、SQLite、镜像、代理
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 生产清单
```

## 1. 概念：交付不是「能跑」

| 维度 | 问题 | 本章做法 |
| --- | --- | --- |
| 活着吗 | 进程僵死 | `/healthz` |
| 能干活吗 | 依赖挂了 | `/readyz` |
| 性能 | 单进程打满 | `--workers` |
| 安全 | root、密钥 | `USER`、`.dockerignore` |
| 退出 | 连接被硬断 | lifespan `finally` |
| 可观测 | 日志丢失 | stdout + 版本头 |

## 2. 机制

### 2.1 两个探针（实测）

```text
依赖正常：/healthz 200，/readyz 200
依赖坏  ：/healthz 200，/readyz 503
```

| 探针 | 谁用 | 失败后果 |
| --- | --- | --- |
| `/healthz` | kubelet livenessProbe | **重启容器** |
| `/readyz` | kubelet readinessProbe / LB | **摘流量**（不重启）|

**反例**：liveness 里查数据库 → 数据库抖动 30 秒 → 全部容器被重启 → 雪崩。

### 2.2 SIGTERM 流程

```text
kubectl delete / docker stop
  → 发 SIGTERM
  → uvicorn 停止接受新连接
  → 等待在途请求（grace period）
  → 跑 lifespan 的 yield 之后部分
  → 退出
  → 超时未退 → SIGKILL
```

实测：`with TestClient` 退出后 `STATE["shutdown_done"] is True`，说明 shutdown 分支真的会执行。

| 风险 | 对策 |
| --- | --- |
| shutdown 里做长任务 | 加超时/改异步 |
| `kill -9` | 无法优雅，只能靠幂等 |
| 关连接池太慢 | 限时 + 强制关闭 |

### 2.3 关文档（实测）

| 配置 | `/docs` | `/openapi.json` | `/items` |
| --- | --- | --- | --- |
| dev | 200 | 200 | 200 |
| prod 形态 | 404 | 404 | 200 |

关的是**暴露面**，不是业务。

## 3. API 逐个拆解

| 参数 | 建议 | 原因 |
| --- | --- | --- |
| `--host 0.0.0.0` | 生产必填 | 容器外不可达 |
| `--port` | 用 `$PORT` | 平台注入 |
| `--workers N` | `2×CPU+1` 以内 | 进程级并行 |
| `--proxy-headers` | 在反代后面必开 | 拿真实 scheme/host |
| `--forwarded-allow-ips` | 只填反代 IP | 防伪造 |
| `--timeout-keep-alive` | 5~75 | 与 LB 对齐 |
| `--log-level` | `info` | 生产不 debug |
| `--reload` | **禁用** | 双进程 + 性能 |
| `--limit-concurrency` | 有背压需求时 | 限并发 |

### 3.1 workers 与共享状态

| 状态 | 多 worker 行为 |
| --- | --- |
| 模块级 dict | **各自一份** |
| `app.state` | 各自一份 |
| SQLite 写 | 锁竞争 |
| 内存广播 | 只覆盖本进程 |

实测未覆盖多进程，标注为**文档约定**。

### 3.2 Dockerfile 要点

| 指令 | 作用 |
| --- | --- |
| `ENV PYTHONUNBUFFERED=1` | 日志不缓冲 |
| 先 `COPY pyproject.toml` | 依赖层缓存 |
| `USER appuser` | 非 root |
| `HEALTHCHECK` | 容器自检 |
| `CMD [...]` exec 形式 | 信号能直达 |

实测 verify 断言：`--workers` 存在且 ≥2、`CMD` 无 `--reload`、最后一条 `USER` 不是 root、`HEALTHCHECK` 打 `/healthz`、`.dockerignore` 含 `.env`。

## 4. 边界条件

### 4.1 探针的副作用

探针会被**高频**调用（每 10 秒）。如果 `/readyz` 每次都连数据库：

| 后果 | 说明 |
| --- | --- |
| 连接数暴涨 | 探针 × 实例数 × 频率 |
| 误判 | 一次抖动就被摘流 |

**对策**：缓存检查结果（如 5 秒内复用），或只检查轻量依赖。

### 4.2 探针与鉴权

探针请求**不带令牌**。如果全局中间件要求鉴权，`/healthz` 返回 401 → 容器永远不健康。必须把探针路径排除。

### 4.3 端口

| 来源 | 优先级 |
| --- | --- |
| `$PORT` | 平台注入（Heroku/Railway 等）|
| `--port` | 默认 8000 |
| 代码里 `uvicorn.run(port=...)` | 只在 `__main__` 有效 |

### 4.4 镜像体积

| 做法 | 效果 |
| --- | --- |
| `python:3.12-slim` | 比 `latest` 小很多 |
| `--no-dev` 装依赖 | 不装 pytest |
| 不拷 `tests/` | `.dockerignore` |
| 多阶段构建 | 进一步瘦身 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| liveness 查 DB | 抖动引发全量重启 | 只查进程 | 实测 |
| readiness 不查依赖 | 流量打到坏实例 | 查关键依赖 | 实测 |
| 只做一个探针 | 重启与摘流混一起 | 两个都要 | 实测 |
| 生产 `--reload` | 性能差/双进程 | 禁用 | 实测 |
| root 运行 | 逃逸风险 | `USER` | 实测 |
| 无 `HEALTHCHECK` | 僵死不被换 | 加探针 | 实测 |
| 日志写文件 | 容器丢日志 | stdout | 第 75 章 |
| 不带 `--proxy-headers` | 全是对代 IP | 开启 | 实测 |
| `forwarded-allow-ips *` | 可伪造 | 收紧 | `[Z3]` |
| workers 过多 | 内存爆 | 按 CPU | `[Z3]` |
| workers + SQLite | 写锁竞争 | 换库/单 worker | 第 59 章 |
| shutdown 长任务 | SIGKILL | 限时 | 第 67 章 |
| `.env` 进镜像 | 密钥泄露 | `.dockerignore` | 实测 |
| `COPY . .` 太早 | 缓存失效 | 先拷依赖清单 | 实测 |
| 基础镜像 `latest` | 不可复现 | 固定版本 | `[Z2]` |
| 探针被鉴权挡 | 永远不健康 | 排除路径 | `-` |
| 探针每次连 DB | 连接暴涨 | 缓存结果 | `-` |
| 不测 503 分支 | 探针形同虚设 | 补故障用例 | 实测 |
| 镜像里带 `.git` | 泄露提交历史与作者信息 | `.dockerignore` 排除 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 探针模板

```python
@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz(response: Response) -> dict[str, Any]:
    if not deps_ok():
        response.status_code = 503
        return {"status": "not ready"}
    return {"status": "ready"}
```

### 6.2 生产清单

| 项 | 检查 |
| --- | --- |
| 两个探针 | ✅ |
| `--workers` | ✅ |
| `--proxy-headers` | ✅ |
| 无 `--reload` | ✅ |
| 非 root | ✅ |
| `.dockerignore` 排除 `.env` | ✅ |
| 日志 stdout | ✅ |
| 关 `/docs`（或加鉴权）| ✅ |
| shutdown 有超时 | ✅ |

### 6.3 交付顺序

```text
1 探针能过（否则编排层起不来）
2 启动命令对（workers/端口/代理）
3 镜像干净（非 root/无密钥）
4 退出优雅（连接不断）
5 再谈性能与灰度
```

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[Z1]` | 官方文档 | https://fastapi.tiangolo.com/zh/deployment/ | 部署总览 |
| `[Z2]` | 文档 | https://docs.docker.com/develop/develop-images/dockerfile_best-practices/ | Dockerfile |
| `[Z3]` | 文档 | https://www.uvicorn.org/deployment/ | 进程与信号 |

> **核对状态**：`[Z1]`–`[Z3]` 为文档链接，**本次未逐页直连复核**；healthz 200、liveness 不查依赖、readyz 200/503、版本头、运行信息、优雅退出、生产关 docs/schema、生产业务可用、Dockerfile 的多 worker/无 reload/非 root/HEALTHCHECK/代理头、`.dockerignore` 排除 `.env` 均为本机实测（静态检查 + `TestClient`），`examples/verify.py` 复现 16/16 通过，`pytest -q` 7 用例全绿。真实 `uvicorn --workers 4` 进程数、SIGTERM 优雅停机、K8s 探针参数、镜像体积、CI 流水线**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 两个探针的差别与后果
- [ ] SIGTERM 到退出发生了什么
- [ ] 为什么 workers 不能配 SQLite
- [ ] 为什么 `.env` 不能进镜像
- [ ] 关文档关的是什么

**能写出（代码层）**：

- [ ] 两个探针
- [ ] 生产启动命令
- [ ] Dockerfile（非 root + HEALTHCHECK）
- [ ] `.dockerignore`
- [ ] 优雅退出验证

**能判断（避坑层）**：

- [ ] 看到 liveness 查 DB → 指出雪崩风险
- [ ] 看到 `--reload` → 指出生产禁用
- [ ] 看到 `COPY . .` → 指出缓存与密钥
- [ ] 看到探针 401 → 指出鉴权排除
- [ ] 看到 shutdown 长任务 → 指出 SIGKILL

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 16/16
- [ ] `docker build` 成功（需你本地执行）
- [ ] 起容器后 `curl localhost:8000/readyz` 为 200

## 9. 下一章衔接

第 77 章起进入 M13 毕业项目：把前面 76 章的能力组装成一个完整的待办服务（CRUD + 分页 + 鉴权 + 错误契约）。

本章留下的伏笔：

1. 探针（76）→ 77 的 `/healthz` 直接复用。
2. 配置（66）、日志（75）、事务（57）→ 78 的生产化改造。
3. 验收清单（各章）→ 79 的 79 条总验收。