# 77 毕业项目（一）：业务实现

## 一句话结论

一个服务「业务完整」的判据不是「接口能跑」，而是**五件事同时成立**：CRUD 全路径、分页信封、三类过滤、写操作鉴权、四种错误（401/404/422/500）**格式统一**。本章的待办服务把这五点做实，实测 22/22：创建 201 带 `Location`、`size=2` 时 `pages=2` 且第二页 1 条、`?q=verify` 与 `?q=VERIFY` 结果相同、无令牌写操作 401 带 `WWW-Authenticate`、422 收敛成 `details.fields[].loc`、500 只回 `internal_error` 不泄露 `RuntimeError`。**最关键的实现细节**：`/stats` 必须注册在 `/{todo_id}` 之前，否则被当成 `int` 解析 → 422。

## 最小可运行案例

```python
# main.py
from fastapi import FastAPI, HTTPException, Response, status

from errors import install_error_handlers
from models import Todo
from store import store

app = FastAPI(title="待办服务", version="0.1.0")
install_error_handlers(app)


@app.post("/todos", response_model=Todo, status_code=201)
def create(title: str, response: Response) -> Todo:
    row = store.create(title)
    response.headers["Location"] = f"/todos/{row['id']}"
    return Todo.model_validate(row)


@app.get("/todos/{todo_id}", response_model=Todo)
def read(todo_id: int) -> Todo:
    row = store.get(todo_id)
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": f"待办 {todo_id} 不存在"})
    return Todo.model_validate(row)
```

```python
# errors.py 的核心：三种异常共用一个信封
def error_body(code: str, message: str, details: dict | None = None) -> dict:
    payload = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return {"error": payload}


async def http_exception_handler(request, exc):
    if isinstance(exc.detail, dict):
        body = error_body(exc.detail.get("code", "error"), exc.detail.get("message", ""))
    else:
        body = error_body(_status_to_code(exc.status_code), str(exc.detail))
    return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)
```

## 怎么跑

```powershell
cd "13-毕业项目\77-业务实现\examples"
uv sync
uv run python verify.py
uv run pytest -q
uvicorn main:app --reload     # 然后打开 http://127.0.0.1:8000/docs
```

预期输出：

```text
[PASS] 创建 201 -> 201 / id=4 / Location
[PASS] 创建后 total+1 -> 3 → 4
[PASS] 分页信封 -> items/total/page/size/pages
[PASS] 分页切分 -> 1,2 | 3
[PASS] 越界页 -> items=[] / total=3
[PASS] 过滤 done -> 只剩 id=2
[PASS] 过滤 priority -> 1 条 high
[PASS] 过滤 q -> verify / VERIFY 同结果
[PASS] 详情 -> 写第 77 章代码
[PASS] 详情 404 契约 -> not_found
[PASS] 部分更新 -> done 变、其余不变
[PASS] 更新 404 -> 404 not_found
[PASS] 删除 204 -> 204 + 后续 404
[PASS] 删除 404 -> 404
[PASS] 写操作要令牌 -> 401 / unauthorized
[PASS] 错令牌 401 -> 401
[PASS] 读操作公开 -> 列表/详情/统计 全 200
[PASS] 422 契约 -> validation_error / body.title
[PASS] query 校验 -> page=0 / size=101 → 422
[PASS] 统计 -> total=3 done=1
[PASS] 500 契约 -> internal_error / 无堆栈
[PASS] 文档完整 -> 5 条路径 / summary 齐全

结果：22/22 通过
```

`pytest -q` 另外 9 个用例全绿。

## 接口契约

| 方法 | 路径 | 鉴权 | 成功码 | 说明 |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/todos` | 否 | 200 | 分页 + 过滤 |
| `POST` | `/api/v1/todos` | **是** | 201 | 带 `Location` |
| `GET` | `/api/v1/todos/stats` | 否 | 200 | 统计 |
| `GET` | `/api/v1/todos/{id}` | 否 | 200/404 | 详情 |
| `PATCH` | `/api/v1/todos/{id}` | **是** | 200/404 | 部分更新 |
| `DELETE` | `/api/v1/todos/{id}` | **是** | 204/404 | 无 body |

查询参数：

| 参数 | 类型 | 约束 | 默认 |
| --- | --- | --- | --- |
| `page` | int | `ge=1` | 1 |
| `size` | int | `ge=1, le=100` | 10 |
| `done` | bool | - | 不过滤 |
| `priority` | enum | `low/medium/high` | 不过滤 |
| `q` | str | `max_length=50` | 不过滤 |

分页信封：

```json
{"items": [...], "total": 3, "page": 1, "size": 10, "pages": 1}
```

错误信封：

```json
{"error": {"code": "not_found", "message": "待办 999 不存在"}}
{"error": {"code": "validation_error", "message": "请求参数不合法",
           "details": {"fields": [{"loc": "body.title", "type": "string_too_short", "msg": "..."}]}}}
```

| `code` | 状态码 | 触发 |
| --- | --- | --- |
| `unauthorized` | 401 | 无/错令牌 |
| `not_found` | 404 | 资源不存在 |
| `validation_error` | 422 | 参数/query 不合法 |
| `internal_error` | 500 | 未捕获异常 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `/stats` 写在 `/{id}` 后 | 422 `int_parsing` | 静态路径在前 |
| 请求/响应共用一个模型 | 客户端能传 `id` | 分开写 |
| 404 用 `str(detail)` | 两种错误格式 | 统一信封 |
| 422 直接返框架结构 | 客户端要解析 `loc` 数组 | 收敛成 `fields[].loc` |
| 500 返回 `str(exc)` | 泄露内部信息 | 通用文案 + 日志 |
| `HTTPBearer()` 默认 `auto_error=True` | 没令牌返 403 且格式不同 | `auto_error=False` |
| 401 不带 `WWW-Authenticate` | 客户端不知道用什么方案 | 加头 |
| PATCH 用 `exclude_unset=False` | 未传字段被覆盖成 None | `exclude_unset=True` |
| DELETE 返 204 还带 body | 协议不合法 | 只返状态 |
| 分页不返回 `pages` | 客户端自己算 | 服务端算好 |
| `size` 无上限 | 一次拉全表 | `le=100` |
| 排序依赖 dict 顺序 | 分页不稳定 | 显式 `sort` |
| 内存 store 不加锁 | 并发写丢数据 | `threading.Lock` |
| 过滤在端点里写 `if` | 越写越乱 | 下沉到 store |
| 错误 `code` 用 HTTP 状态文本 | 客户端难分支 | 自定义稳定 `code` |

## 毕业自查

- [ ] 六个端点全部按契约实现
- [ ] 四种错误响应格式完全一致
- [ ] `/stats` 不被 `/{id}` 吞掉
- [ ] 分页信封含 `pages`
- [ ] 写操作鉴权、读操作公开
- [ ] 动手题一：加 `PATCH /todos/{id}/toggle` 一键切换 `done`
- [ ] 动手题二：加 `?sort=created_at&order=desc` 排序参数

> 想看错误处理器的注册顺序、`HTTPException.detail` 的两种形态、鉴权依赖的三种写法、分页 SQL 对应关系、18 条坑，继续读 [`base.md`](./base.md)。