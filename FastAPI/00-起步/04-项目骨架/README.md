# 04 项目骨架

## 一句话结论

`APIRouter` 是「小号 FastAPI」，只负责一组路由；`include_router` 把多个 router 叠加成一个应用。前缀是**逐层拼接**的：`/api` + `/v1` + `/items` = `/api/v1/items`，少一层就 404。

学完这一章，你能：把 2000 行的 `main.py` 拆成可维护的目录树、说清 `prefix` 与 `tags` 的叠加规则、避开循环导入。

## 最小可运行案例

```text
examples/
└── shop/
    ├── __init__.py
    ├── main.py              ← create_app() + app 实例
    ├── core/
    │   ├── __init__.py
    │   └── config.py        ← Settings
    └── api/
        ├── __init__.py
        └── v1/
            ├── __init__.py
            ├── router.py    ← 汇总 v1 下所有资源
            ├── items.py     ← APIRouter(prefix="/items")
            └── users.py     ← APIRouter(prefix="/users")
```

三层前缀分别写在三个文件里：

```python
# main.py
app.include_router(api_router, prefix="/api")        # 第 1 层

# api/v1/router.py
api_router = APIRouter(prefix="/v1")                 # 第 2 层
api_router.include_router(items.router)

# api/v1/items.py
router = APIRouter(prefix="/items", tags=["商品"])   # 第 3 层
@router.get("")
def list_items(): ...
```

最终地址：`GET /api/v1/items`。

## 怎么跑

```powershell
cd "00-起步\04-项目骨架\examples"

# 启动（注意模块路径是 shop.main，不是 main）
uv run uvicorn shop.main:app --reload

# 或直接验收
uv run python verify.py
```

预期输出：

```text
[PASS] 包可导入 -> shop.__version__=0.1.0
[PASS] 三层前缀叠加 -> /api/v1/items | /api/v1/items/1 | /api/v1/users 均 200
[PASS] 前缀缺一层即 404 -> /v1/items /api/items /items 均 404
[PASS] /health 不版本化 -> {'status': 'ok', 'env': 'dev'}
[PASS] tags 随子 router 保留 -> items=['商品'] users=['用户'] health=['运维']
[PASS] 空前缀 + 尾斜杠 307 -> /api/v1/items 200；带尾斜杠 307 -> .../api/v1/items
[PASS] 精确路径仍优先 -> {'latest': '苹果'}
[PASS] 工厂函数隔离 -> create_app() 返回不同实例：True，路由数 6/6
[PASS] OpenAPI 路径完整 -> 6 条
[PASS] 配置单例 -> env=dev api_prefix=/api debug=False

结果：10/10 通过
```

常见启动失败：

| 报错 | 原因 | 解决 |
| --- | --- | --- |
| `Could not import module "shop.main"` | 不在 `examples` 目录 | `cd examples` 或加 `--app-dir examples` |
| `ImportError: attempted relative import with no known parent package` | 直接运行了包内模块（`python api/v1/items.py`） | 用 `uvicorn shop.main:app` 启动 |
| `ModuleNotFoundError: No module named 'shop'` | `examples` 不在 `sys.path` | 在 `examples` 目录执行 |

## 核心 API 速查

| API | 作用 | 关键参数 |
| --- | --- | --- |
| `APIRouter()` | 创建路由集合 | `prefix`、`tags`、`dependencies`、`responses`、`default_response_class` |
| `router.include_router(sub)` | 挂载子 router | `prefix`、`tags`、`dependencies` |
| `app.include_router(router)` | 挂到应用 | 同上 |
| `APIRouter(prefix=...)` | 路径前缀 | **不能**以 `/` 结尾，**不能**含 `{param}` |
| `APIRouter(tags=[...])` | 文档分组 | 与父级 tags **叠加**而不是覆盖 |

| 前缀层级 | 写法 | 结果 |
| --- | --- | --- |
| 1 层 | `include_router(r, prefix="/api")` | `/api/...` |
| 2 层 | 子 router `prefix="/v1"` | `/api/v1/...` |
| 3 层 | 孙 router `prefix="/items"` | `/api/v1/items/...` |
| 空前缀 | `@router.get("")` | `/api/v1/items` |
| 斜杠前缀 | `@router.get("/")` | `/api/v1/items/`（触发 307） |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `prefix="/items/"` 带尾斜杠 | 拼出 `//`，路径变成 `/api/v1/items//{id}` | `prefix="/items"` |
| `include_router(r, prefix="/api/")` | 同上 | 去掉尾斜杠 |
| `@router.get("")` 与 `@router.get("/")` 混用 | 实测两者**可共存**但 `/x` 与 `/x/` 一个 200 一个 307 | 统一用 `""` |
| 用 `prefix="/items/{item_id}"` | `include_router` 报路径参数错误 | 参数写在具体接口上 |
| `python api/v1/items.py` 直接跑 | 相对导入报错 | `uvicorn shop.main:app` |
| 忘记 `__init__.py` | 现代 Python 能靠命名空间包导入，但工具链易出错 | 显式创建 |
| `main.py` 里写业务逻辑 | 无法复用、测试要起整个 app | 业务放 `api/v1/*.py` |
| 模块间互相 `import` | `ImportError: partially initialized module` | 见 `base.md` 4.4 三种解法 |
| 把所有资源塞进 `router.py` | 又变回大文件 | 一资源一文件 |

## 毕业自查

- [ ] 能画出这套骨架的目录树，并说出每层职责
- [ ] 能说出三层前缀分别写在哪三个文件
- [ ] 能解释 `@router.get("")` 与 `@router.get("/")` 的差别
- [ ] 能说出 `tags` 是叠加还是覆盖（实测：叠加）
- [ ] 能解释为什么 `python items.py` 会报相对导入错误
- [ ] 能说出循环导入的至少两种解法
- [ ] 能解释为什么要用 `create_app()` 工厂函数
- [ ] 动手题一：新增 `GET /api/v1/orders`，只改两个文件
- [ ] 动手题二：把 `api_prefix` 改成 `/gateway`，确认所有路径随之变化

> 想看导入机制、循环导入三种解法、`src/` 布局、34 条坑，继续读 [`base.md`](./base.md)。
