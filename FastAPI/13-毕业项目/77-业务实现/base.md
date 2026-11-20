# 77 毕业项目（一）· 业务实现 · 完整版（base.md）

> `README.md` 给你接口契约与验收输出；本文件把「错误信封怎么设计、三种异常怎么合并、鉴权依赖为什么这么写、分页与过滤为什么下沉到 store、`/stats` 为什么必须前置」拆开。学完这章，你能从零交付一个接口契约自洽的服务。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 05 章（响应）、第 09 章（错误处理）、第 65 章（拆分） |
| 覆盖范围 | CRUD、分页、过滤、鉴权、统一错误契约 |
| 明确不覆盖 | 真实数据库、排序参数、软删除、乐观锁 |
| 学完验收 | 能跑通 `verify.py` 22/22 与 `pytest -q` 9 用例 |

## 0. 怎么用这份文件

**依据约定**：`` `[a]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 业务完整的五个判据
2 机制（第 2 节）    → 错误合并与路由顺序
3 API（第 3 节）     → 分页/过滤/鉴权
4 边界（第 4 节）    → 并发、越界页、204
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 文件划分与契约表
```

## 1. 概念：五个判据

| 判据 | 反例 | 本章做法 |
| --- | --- | --- |
| CRUD 全路径 | 只有 POST/GET | 5 个操作 + stats |
| 分页信封 | 只返 `list` | `items/total/page/size/pages` |
| 过滤 | 客户端自己筛 | `done/priority/q` 服务端过滤 |
| 鉴权边界 | 全都保护或都不保护 | 写保护、读公开 |
| 错误统一 | 404 字符串、422 框架结构 | 单一信封 |

## 2. 机制

### 2.1 三类异常合并（实测）

| 异常 | 谁抛 | 处理器 |
| --- | --- | --- |
| `HTTPException` | 业务主动 | `http_exception_handler` |
| `RequestValidationError` | FastAPI 校验失败 | `validation_exception_handler` |
| `Exception` | 未捕获 | `unhandled_exception_handler` |
| `AppError`（自定义） | 领域逻辑 | `app_error_handler` |

注册顺序不影响匹配（按类型精确匹配），但**必须都注册**，否则漏一类就多一种格式。

### 2.2 `detail` 的两种形态

```python
raise HTTPException(404, detail="待办不存在")                    # 字符串
raise HTTPException(404, detail={"code": "not_found", "message": "..."})  # 字典
```

处理器里用 `isinstance` 分支。**推荐只用字典**，字符串形态只是为了兼容框架内部抛出的异常（如 405）。

### 2.3 路由注册顺序（实测）

```text
/stats 在 /{todo_id} 之前 → 200，返回统计
/stats 在 /{todo_id} 之后 → 422（int_parsing）
```

因为 Starlette 按注册顺序匹配，`/{todo_id}` 会先命中并试图把 `stats` 转成 `int`。

### 2.4 鉴权为什么用 `auto_error=False`（实测）

| 写法 | 没带令牌 |
| --- | --- |
| `HTTPBearer()` | 403，body 是框架默认 `{"detail": ...}` |
| `HTTPBearer(auto_error=False)` | 我们自己抛 401 + 统一契约 |

实测没令牌时返回 `401 / unauthorized`，且带 `WWW-Authenticate: Bearer`。

## 3. API 逐个拆解

### 3.1 分页

```python
pages = (total + size - 1) // size     # 向上取整
start = (page - 1) * size
items = rows[start : start + size]
```

| 情形 | 实测 |
| --- | --- |
| `size=2`，3 条 | `pages=2`，第二页 1 条 |
| `page=99` | `items=[]`，`total` 不变 |
| `page=0` | 422（`ge=1`） |
| `size=101` | 422（`le=100`） |

### 3.2 过滤组合

| 参数 | 实现 | 实测 |
| --- | --- | --- |
| `done=true` | `row["done"] is done` | 只剩 id=2 |
| `priority=high` | 枚举相等 | 1 条 |
| `q=verify` | `q.lower() in title.lower()` | 与 `VERIFY` 同结果 |

三者可叠加，过滤在 `store.list()` 里统一做。

### 3.3 鉴权依赖链

```text
HTTPBearer(auto_error=False)
  → get_current_user  (没令牌/错令牌 → 401)
    → require_writer   (写操作挂)
```

| 端点 | 依赖 |
| --- | --- |
| `POST` / `PATCH` / `DELETE` | `Writer` |
| `GET` | 无 |

### 3.4 201 的 `Location`

```python
response.headers["Location"] = f"/api/v1/todos/{row['id']}"
```

实测 `Location: /api/v1/todos/4`。客户端可直接 GET，无需解析 body。

## 4. 边界条件

### 4.1 并发写

内存 store 用 `threading.Lock` 包住读改写。去掉锁后并发 `POST` 会出现 id 重复或丢记录（本章未做压力测试，仅代码层保证）。

### 4.2 204 不能有 body

```python
return Response(status_code=204)
```

实测 `response.text == ""`。若返回 dict，Starlette 会报错或发出非法响应。

### 4.3 越界页不报错

`page=99` 返回 `items=[]`。**不要**返回 404 —— 客户端翻页到底是很正常的操作。

### 4.4 500 不泄露

| 返回内容 | 是否可接受 |
| --- | --- |
| `str(exc)` | ❌ 泄露内部 |
| `traceback` | ❌ 泄露源码结构 |
| `internal_error` + 通用文案 | ✅ |

实测响应体里 `内部炸了`、`RuntimeError` 都不出现。

### 4.5 存储层与 HTTP 层分离

`store.py` 里没有任何 `HTTPException`；`todos_router.py` 里没有任何数据操作细节。换成 SQL 时只改 `store.py`。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `/stats` 在 `/{id}` 后 | 422 `int_parsing` | 静态路径前置 | 实测 |
| 请求/响应共用模型 | 客户端能传 `id` | 分开定义 | 实测 |
| 404 用字符串 detail | 两种错误格式 | 统一信封 | 实测 |
| 422 返框架原始结构 | 客户端解析 `loc` 数组 | 收敛成 `fields` | 实测 |
| 500 返回 `str(exc)` | 泄露内部 | 通用文案 | 实测 |
| `HTTPBearer()` 默认 | 403 + 格式不一 | `auto_error=False` | 实测 |
| 401 缺 `WWW-Authenticate` | 客户端不知方案 | 加头 | 实测 |
| PATCH `exclude_unset=False` | 未传字段被置 None | `exclude_unset=True` | 实测 |
| DELETE 带 body | 协议非法 | 只返 204 | 实测 |
| 分页不返 `pages` | 客户端自己算 | 服务端算 | 实测 |
| `size` 无上限 | 全表拉取 | `le=100` | 实测 |
| 排序依赖 dict 顺序 | 分页不稳 | 显式 `sort` | 实测 |
| 越界页返 404 | 客户端翻页报错 | 返空列表 | 实测 |
| store 无锁 | 并发丢数据 | `threading.Lock` | 实测 |
| 过滤逻辑写在端点 | 越写越乱 | 下沉到 store | 实测 |
| 错误 `code` 用状态文本 | 客户端难分支 | 自定义稳定 code | 实测 |
| 只注册 `HTTPException` 处理器 | 422 格式不同 | 三类都注册 | 实测 |
| 鉴权写在每个端点里 | 漏一处就裸奔 | 依赖统一挂 | 实测 |
| 端点直接操作 `store._items` | 绕过锁与过滤 | 只调公开方法 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 文件划分

```text
examples/
├── main.py           # 装配：app + 处理器 + 路由
├── models.py         # 数据契约
├── store.py          # 数据存取（无 HTTP）
├── errors.py         # 错误契约 + 处理器
├── security.py       # 鉴权依赖
├── todos_router.py   # 端点编排
├── tests/test_todos.py
└── verify.py
```

| 层 | 允许依赖 | 禁止 |
| --- | --- | --- |
| `models` | pydantic | 任何 IO |
| `store` | stdlib | 任何 HTTP 概念 |
| `security` | fastapi | 数据操作 |
| `router` | 以上全部 | 直接操作 `_items` |

### 6.2 契约表先写

动手前把这张表填满，接口就不会边写边变：

| 维度 | 必须明确 |
| --- | --- |
| 幂等性 | `PUT`/`DELETE` 幂等，`POST` 不幂等 |
| 成功码 | 200 / 201 / 204 |
| 错误码 | 401 / 404 / 422 / 500 |
| 分页 | 参数名 + 信封字段 |
| 鉴权 | 哪些端点保护 |

### 6.3 验收优先级

```text
1 错误格式一致（客户端最先崩的地方）
2 分页信封（前端最先依赖的地方）
3 路由顺序（最隐蔽的 bug）
4 鉴权边界（最危险的地方）
```

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[a1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/handling-errors/ | 异常处理器 |
| `[a2]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/security/http-basic-auth/ | 安全依赖 |
| `[a3]` | 文档 | https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Status/201 | 201 + Location |

> **核对状态**：`[a1]`–`[a3]` 为文档链接，**本次未逐页直连复核**；201 与 `Location`、total 递增、分页信封、`size=2` 切分、越界页、三类过滤（含大小写）、详情、404 契约、部分更新、更新 404、204 无 body、删除 404、401 三种情况、422 契约、query 校验、统计、500 契约、文档完整性均为本机实测，`examples/verify.py` 复现 22/22 通过，`pytest -q` 9 用例全绿。真实数据库、并发压测、软删除、排序参数、乐观锁**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 业务完整的五个判据
- [ ] 三类异常为什么要合并
- [ ] `/stats` 为什么必须前置
- [ ] `auto_error=False` 的作用
- [ ] 越界页为什么返空而不是 404

**能写出（代码层）**：

- [ ] 统一错误信封
- [ ] 分页信封与向上取整
- [ ] 部分更新语义
- [ ] 写操作鉴权依赖
- [ ] 201 + Location

**能判断（避坑层）**：

- [ ] 看到 422 `int_parsing` → 想到路由顺序
- [ ] 看到两种错误格式 → 想到处理器没注册全
- [ ] 看到 403 而非 401 → 想到 `auto_error`
- [ ] 看到 PATCH 清空字段 → 想到 `exclude_unset`
- [ ] 看到 500 带异常信息 → 想到泄露

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 22/22
- [ ] `uv run pytest -q` 全绿
- [ ] 打开 `/docs` 手动点一遍六个端点

## 9. 下一章衔接

第 78 章 `毕业项目（二）：生产化改造`：配置外置、结构化日志、请求 ID、SQLite 事务、依赖注入重构。

本章留下的伏笔：

1. `DEMO_TOKEN` 硬编码（77）→ 78 从配置读。
2. `store` 是模块级单例（77）→ 78 改成 `Depends`，测试可覆盖。
3. 内存数据重启即丢（77）→ 78 换 SQLite + 事务边界。
4. 没有请求日志（77）→ 78 加中间件。