# 56 仓储层分层

## 一句话结论

把「HTTP / 业务 / SQL」拆成三层，每层只有一个变化理由：`router.py` 只做参数绑定与异常翻译，`service.py` 只做业务规则，`repository.py` 只有 SQL。分层的直接收益不是好看，而是**可替换**——实测用 `app.dependency_overrides[get_repository]` 换掉数据库，路由和 service 一行不改就返回假数据。两个实测坑：`/items/count` 会被 `/items/{item_id}` 先匹配成 **422 `int_parsing`**（不是 404）；`with sqlite3.connect(...) as conn` **不关闭连接**，Windows 上导致 `WinError 32`。

## 目录结构

```text
examples/
  db.py          连接、建表、get_db 依赖
  models.py      领域模型 + 领域异常
  repository.py  只有 SQL
  service.py     只有业务规则
  router.py      只有 HTTP 语义
  main.py        组装（lifespan + include_router）
```

## 最小可运行案例

```python
# repository.py
class ItemRepository:
    def __init__(self, conn): self._conn = conn

    def find_by_name(self, name: str) -> Item | None:
        row = self._conn.execute("SELECT id, name, price FROM items WHERE name = ?", (name,)).fetchone()
        return Item(**dict(row)) if row else None


# service.py
class ItemService:
    def __init__(self, repository): self._repository = repository

    def create_item(self, payload: ItemCreate) -> Item:
        if self._repository.find_by_name(payload.name) is not None:
            raise DuplicateItemError(payload.name)
        return self._repository.add(payload.name, payload.price)


# router.py
@router.post("", response_model=Item, status_code=201)
def create_item(payload: ItemCreate, service: ServiceDep) -> Item:
    try:
        return service.create_item(payload)
    except DuplicateItemError as exc:
        raise HTTPException(status_code=409, detail=f"名称已存在：{exc.name}") from exc
```

## 怎么跑

```powershell
cd "09-数据持久化\56-仓储层分层\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 空列表 -> []
[PASS] 创建 201 -> id=1
[PASS] 重名 409 -> 409
[PASS] 详情 -> {'id': 1, 'name': 'a', 'price': 7}
[PASS] 不存在 404 -> 404
[PASS] 删除 204→404 -> 204 → 404
[PASS] 路由顺序陷阱 -> 422 int_parsing（被 /{item_id} 吃掉）
[PASS] 计数端点 -> count=3
[PASS] 仓储可替换 -> 返回假数据，未碰数据库
[PASS] 仓储无 HTTP -> 无 HTTPException/status_code/APIRouter/Depends
[PASS] 服务层纯净 -> 无 SQL、无 HTTP，只有领域异常
[PASS] 路由层无 SQL -> 无任何 SQL 关键字
[PASS] OpenAPI 路径 -> /items,/items/_/count,/items/{item_id}
[PASS] 响应模型 -> Item 进入 components.schemas

结果：14/14 通过
```

## 核心 API 速查

| 层 | 该出现 | 不该出现 |
| --- | --- | --- |
| `router.py` | `APIRouter`、`Depends`、`HTTPException`、`response_model` | 任何 SQL、业务判断 |
| `service.py` | 领域规则、领域异常 | SQL、HTTP 状态码 |
| `repository.py` | SQL、`sqlite3.Row` | HTTP、Pydantic 请求模型 |
| `db.py` | `connect`、`get_db`、建表 | 业务语义 |
| `models.py` | Pydantic 模型、领域异常 | 数据库连接 |

| 实测行为 | 结果 |
| --- | --- |
| 重名 | service 判定 → `DuplicateItemError` → 409 |
| 不存在 | `ItemNotFoundError` → 404 |
| 删除成功/失败 | 204 / 404 |
| `GET /items/count` | **422 `int_parsing`**（被 `/{item_id}` 吃掉）|
| `GET /items/_/count` | 正常 |
| 替换仓储 | `dependency_overrides` 生效，代码不改 |
| OpenAPI | 分层不影响生成 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 路由里写 SQL | 换库要改路由 | 移到 repository |
| 路由里做业务判断 | 规则散落 | 移到 service |
| service 抛 `HTTPException` | 业务耦合 HTTP | 抛领域异常，router 翻译 |
| 把 `sqlite3.Row` 传到 service | 泄漏存储细节 | 转成 Pydantic 模型 |
| 用 `with sqlite3.connect() as conn` | **不关闭连接**（WinError 32）| 显式 `close()` |
| 静态路径写在 `/{id}` 后面 | 422/被吞 | 具体路径优先，或用多段前缀 |
| 仓储里 `commit()` | 一次请求多次提交，事务边界碎 | 上移到依赖（第 57 章）|
| 每层都做参数校验 | 重复 | 入口一次 |
| 为了分层加 5 层抽象 | 读代码要跳 6 个文件 | 三层足够 |
| 仓储返回 `dict` | 无类型、无校验 | 返回模型 |
| 测试直接连真库 | 数据污染 | `dependency_overrides` |
| `get_db` 里不 `close` | 连接泄漏 | `finally: close()` |
| 路由函数里 `try/except Exception` | 掩盖真实错误 | 只捕获具体领域异常 |

## 毕业自查

- [ ] 能画出三层的调用方向与依赖注入链
- [ ] 能说出每层「不该出现什么」
- [ ] 能用 `dependency_overrides` 换仓储写测试
- [ ] 能解释领域异常为什么要翻译
- [ ] 知道 `with sqlite3.connect()` 不关连接
- [ ] 动手题一：把 `get_repository` 换成 mock 并写 3 个 service 单测
- [ ] 动手题二：加 `PATCH /items/{id}` 走完整三层

> 想看每层的判据来源、领域异常与 HTTP 的映射表、分层的代价与何时不该分层、`get_db` 到事务的演进、18 条坑，继续读 [`base.md`](./base.md)。