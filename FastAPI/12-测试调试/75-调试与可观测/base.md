# 75 调试与可观测 · 完整版（base.md）

> `README.md` 给你能跑的中间件与 `caplog` 断言；本文件把「日志为什么必须结构化、请求 ID 怎么串起一次调用、`debug=True` 到底泄露什么、契约快照怎么维护」拆开。学完这章，你能在 30 秒内定位一个线上 500。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 52 章（中间件）、第 69 章（OpenAPI） |
| 覆盖范围 | 请求日志、请求 ID、异常兜底、`debug` 风险、契约快照 |
| 明确不覆盖 | OpenTelemetry 全链路、Prometheus 指标、日志采集管道 |
| 学完验收 | 能跑通 `verify.py` 16/16、能说出 `debug=True` 泄露了什么 |

## 0. 怎么用这份文件

**依据约定**：`` `[Yn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 可观测的三根柱子
2 机制（第 2 节）    → 中间件顺序与请求 ID
3 API（第 3 节）     → logging / caplog / 契约
4 边界（第 4 节）    → debug、脱敏、慢请求、404
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 日志字段与告警
```

## 1. 概念：日志、指标、追踪

| 柱子 | 本章覆盖 | 生产常见工具 |
| --- | --- | --- |
| 日志 | ✅ 一行一请求 + 请求 ID | ELK / Loki |
| 指标 | ⚠️ 只提耗时阈值 | Prometheus |
| 追踪 | ⚠️ 只做请求 ID 透传 | OpenTelemetry |

**先用好日志**：90% 的排障靠「找到那个请求的那一行」。

## 2. 机制

### 2.1 中间件的包裹关系

```text
请求 → [observe 中间件] → 路由 → 端点
                     ← 响应 ←
```

所以中间件能：

| 能力 | 实现 |
| --- | --- |
| 生成/沿用请求 ID | 读 header，否则 `uuid4().hex[:8]` |
| 计时 | `perf_counter()` 前后夹 |
| 兜异常 | `try/except` + 兜底 `JSONResponse` |
| 加响应头 | `response.headers[...]` |

### 2.2 请求 ID（实测）

```text
GET /items                       → X-Request-ID: dbdfd26f（自动生成，8 位）
GET /items  X-Request-ID: trace-42 → X-Request-ID: trace-42（沿用）
```

**单进程内不唯一**：`uuid4().hex[:8]` 是 32 位空间，量级小时够用；高并发要加时间前缀或直接用完整 uuid。

### 2.3 异常兜底（实测）

```text
GET /boom
→ status 500
→ body {"detail": "internal server error", "request_id": "baa8dfea"}
→ header X-Request-ID: baa8dfea   ← 与 body 一致
→ 日志 ERROR: request failed method=GET path=/boom elapsed_ms=1.02
```

这三点一致，才能「用户报错 → 拿到 ID → 搜日志」。

### 2.4 `debug=True` 泄露什么（实测）

| 配置 | body |
| --- | --- |
| `debug=False` | `{"detail": "internal server error", ...}` |
| `debug=True` | **3699 字节的 HTML traceback**，含文件路径、函数名、局部变量 |

生产开 `debug=True` 等于把源码结构送给攻击者。

## 3. API 逐个拆解

| API | 说明 |
| --- | --- |
| `logging.getLogger("app.request")` | 独立命名空间，便于按 logger 过滤 |
| `logger.log(level, fmt, *args, extra={...})` | 动态级别 |
| `logger.exception(...)` | 自动附 `exc_info` |
| `caplog.set_level(level, logger=name)` | 测试里控制捕获级别 |
| `record.getMessage()` | 断言用 |
| `getattr(record, "request_id", None)` | 断言自定义字段 |

### 3.1 慢请求升级（实测）

```text
50ms 阈值：/slow (102ms) → WARNING
           /items (1.66ms) → INFO
```

好处：`grep WARNING` 就是全部慢请求，不用扫全量日志。

### 3.2 契约快照（实测）

```text
paths:       ["/boom", "/items", "/login", "/missing", "/slow"]
operationId: ["boom_boom_get", "list_items_items_get", "login_login_post",
              "missing_missing_get", "slow_slow_get"]
```

| 变化 | 含义 |
| --- | --- |
| 路径增删 | 破坏性改动，必须 review |
| operationId 变 | 函数改名/路径改名，前端代码生成会变 |
| `summary` 缺失 | 文档质量下降 |

## 4. 边界条件

### 4.1 脱敏（实测）

```python
SENSITIVE_KEYS = {"password", "token", "secret", "authorization"}

sanitize({"username": "u", "password": "hunter2"})
# → {"username": "u", "password": "***"}
```

实测日志里 `hunter2` 不出现、`***` 出现。

**不够**：嵌套 dict、列表里的敏感字段、query 参数里的 `?token=`，都需要递归处理。本章只演示单层。

### 4.2 404 不被吞（实测）

业务 `HTTPException(404)` 走正常异常处理，中间件的 `try/except` **只兜 `Exception` 里未被 Starlette 处理的**部分。实测：

```text
GET /missing → 404 {"detail": "not here"}
```

如果中间件写成 `except Exception: return 500` 且不区分 `HTTPException`，就会把 404 变成 500。本章的写法是先 `call_next`（异常在更内层处理），所以安全。

### 4.3 日志不该写文件

| 环境 | 建议 |
| --- | --- |
| 容器 | stdout，由运行时收集 |
| 传统服务器 | 文件 + logrotate |
| Serverless | stdout |

写文件在容器里会随容器销毁丢失。

### 4.4 性能

`perf_counter()` 两次调用约 0.1μs；一行日志约 1-5μs（同步 handler）。每秒 1 万请求时日志可能成为瓶颈，考虑异步 handler 或采样。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 生产开 `debug=True` | 泄露 traceback（实测 3699 字节）| 默认关闭 | 实测 |
| 日志打完整 body | 密码进日志 | 白名单脱敏 | 实测 |
| 只用 `print` | 无级别、无关联 | `logging` | 实测 |
| 日志缺请求 ID | 无法串联 | `extra` | 实测 |
| 中间件不兜异常 | 500 无 ID | `try/except` | 实测 |
| `logger.error` 不带堆栈 | 查不到现场 | `logger.exception` | 实测 |
| 日志写文件 | 容器里丢 | stdout | `[Y3]` |
| 耗时才秒 | 精度不足 | 毫秒 | 实测 |
| 阈值硬编码 | 环境不同 | 配置化 | 实测 |
| `capsys` 断文本 | 脆弱 | `caplog` | 实测 |
| `caplog` 不设级别 | 捕不到 INFO | `set_level` | 实测 |
| 契约变化无感知 | 前端突然坏 | 快照断言 | 实测 |
| 只断路径 | 改名漏检 | 加 operationId | 实测 |
| 不检查 `summary` | 文档差 | 强制断言 | 实测 |
| 中间件顺序错 | 耗时不准 | 放最外层 | 第 52 章 |
| `request.state` 未赋值就用 | AttributeError | 中间件先赋值 | 实测 |
| 多 handler 重复输出 | 日志翻倍 | 统一配置 | `[Y1]` |
| 只测 happy path | 500 无人管 | 补异常用例 | 实测 |
| 日志里打完整 URL | `?token=` 之类的敏感参数进日志 | 只打 `path` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 日志字段

| 字段 | 必需 |
| --- | --- |
| `request_id` | ✅ |
| `method` / `path` | ✅ |
| `status` | ✅ |
| `elapsed_ms` | ✅ |
| `user_id` | 建议 |
| `trace_id` | 有链路时 |

### 6.2 目录

```text
examples/
├── main.py
├── pyproject.toml
├── tests/
│   └── test_observability.py
└── verify.py
```

### 6.3 断言矩阵

| 维度 | 断言 |
| --- | --- |
| ID | 存在、可透传、500 时一致 |
| 日志 | 一行、含字段、级别正确 |
| 脱敏 | 无明文、有掩码 |
| 安全 | `debug=False` 无 traceback |
| 契约 | 路径与 operationId 稳定 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[Y1]` | 文档 | https://docs.python.org/3/library/logging.html | `logging` |
| `[Y2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/debugging/ | `debug` |
| `[Y3]` | 方法论 | https://12factor.net/zh_cn/logs | 日志当事件流 |

> **核对状态**：`[Y1]`–`[Y3]` 为文档/方法论链接，**本次未逐页直连复核**；请求 ID 生成与透传、耗时头、一行日志、关联 ID、慢请求 WARNING（102ms）、快请求 INFO（1.66ms）、500 带 ID、500 记 ERROR、`debug=True` 3699 字节 traceback、生产隐藏、404 正常、契约路径与 operationId、summary 齐全、密码脱敏均为本机实测，`examples/verify.py` 复现 16/16 通过，`pytest -q` 10 用例全绿。递归脱敏、异步日志 handler、Prometheus、OpenTelemetry、uvicorn 日志接管**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 为什么日志要结构化
- [ ] 请求 ID 怎么串起调用
- [ ] `debug=True` 泄露什么
- [ ] 为什么 404 不会被中间件吞
- [ ] 契约快照防的是什么

**能写出（代码层）**：

- [ ] 请求 ID 中间件
- [ ] 一行日志
- [ ] 异常兜底
- [ ] 脱敏函数
- [ ] `caplog` 断言

**能判断（避坑层）**：

- [ ] 看到生产开 `debug` → 立刻指出泄露
- [ ] 看到日志有密码 → 指出脱敏
- [ ] 看到 500 无 ID → 指出中间件没兜
- [ ] 看到 `print` → 指出不可观测
- [ ] 看到契约变更无人知 → 加快照

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 16/16
- [ ] `uv run pytest -q` 全绿
- [ ] 打开 `/docs` 确认每个端点都有 summary

## 9. 下一章衔接

第 76 章 `部署与交付`：`uvicorn` 参数、健康检查、容器化、优雅退出。

本章留下的伏笔：

1. 日志到 stdout（75）→ 76 讲容器化部署时日志怎么被收集。
2. 健康检查（75 未涉及）→ 76 的 `/healthz` 与 `/readyz`。
3. `debug` 开关（75）→ 76 用环境变量控制生产配置。