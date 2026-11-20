# 04 项目骨架 · 完整版（base.md）

> `README.md` 给你目录树；本文件把「Python 导入机制、prefix 怎么拼、为什么会循环导入、`src/` 布局解决什么」逐条拆开。学完这章，你要能独立设计一个 50 个接口也不会乱的项目结构。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Python 3.12.8（本机实测） |
| 前置 | 第 03 章（路由与方法）、`py-base/05-…/21-模块化` |
| 覆盖范围 | 包与模块、`APIRouter` 三层结构、prefix/tags 叠加、绝对与相对导入、循环导入、应用工厂、`src/` 布局 |
| 明确不覆盖 | 配置管理细节（66）、依赖注入的 `dependencies`（39）、多版本并存策略（65） |
| 学完验收 | 能跑通 `verify.py` 10/10、能解释三层前缀、能说出循环导入两种解法 |

## 0. 怎么用这份文件

**依据约定**：`` `[Pn]` `` 指向第 7 节；标「实测」的为本机输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 包、模块、导入路径
2 机制（第 2 节）    → include_router 到底做了什么（重点）
3 API（第 3 节）     → prefix / tags / dependencies 叠加规则
4 边界（第 4 节）    → 尾斜杠、空路径、循环导入、src 布局
5 注意事项（第 5 节）→ 34 条对照
6 最佳实践（第 6 节）→ 目录模板
```

## 1. 概念：包、模块、导入路径

| 概念 | 定义 | 例子 | 依据 |
| --- | --- | --- | --- |
| 模块（module） | 一个 `.py` 文件 | `items.py` | `[P1]` |
| 包（package） | 含 `__init__.py` 的目录 | `shop/` | `[P1]` |
| 子包 | 包里的包 | `shop/api/` | `[P1]` |
| 模块路径 | 用 `.` 连接的导入名 | `shop.api.v1.items` | `[P1]` |
| `sys.path` | 解释器查找模块的目录列表 | `['', ...]` | `[P2]` |

`uvicorn shop.main:app` 能工作的前提：

| 条件 | 说明 | 依据 |
| --- | --- | --- |
| 当前工作目录在 `examples` | `''` 会作为第一个 `sys.path` 项 | `[P2]` |
| `shop/__init__.py` 存在 | 否则可能被当成命名空间包（能导入但工具链易出错） | `[P1]` |
| `shop/main.py` 里有模块级 `app` | 服务器用 `getattr` 取值 | `[P3]` |

> 注意：`shop.main:app` 冒号左边是**导入路径**，右边是**变量名**。所以「模块导入失败」和「变量不存在」是两种不同错误：前者是 `Could not import module`，后者是 `AttributeError`。

## 2. 机制：`include_router` 做了什么

```python
app.include_router(api_router, prefix="/api")
```

四步（依据 `[P3]`）：

```text
① 遍历 api_router.routes（每个都是 APIRoute）
② 对每条路由，把 path 拼成 prefix + route.path
③ tags 取并集：父级 tags + 子级 tags（不是覆盖）
④ 复制一份 APIRoute，追加到 app.routes 末尾（顺序 = include 顺序）
```

| 步骤 | 实测证据 |
| --- | --- |
| ② | `/api` + `/v1` + `/items` → `/api/v1/items` |
| ③ | `/api/v1/items` 的 tags 是 `["商品"]` |
| ④ | 先 include 的 router 优先级更高 |

### 2.1 三层前缀的完整拼接链

```text
main.py        include_router(api_router, prefix="/api")
                 ↓
router.py      APIRouter(prefix="/v1")
                 ↓
items.py       APIRouter(prefix="/items")
                 ↓
items.py       @router.get("")            → 空串，不贡献路径段
                 ↓
最终           /api + /v1 + /items + "" = /api/v1/items
```

实测四种访问：

```text
GET /api/v1/items    -> 200
GET /api/v1/items/1  -> 200
GET /api/v1/users    -> 200
GET /v1/items        -> 404   （少了 /api）
GET /api/items       -> 404   （少了 /v1）
GET /items           -> 404   （少了两层）
```

| 结论 | 说明 |
| --- | --- |
| 前缀是**拼接**，不是「任选其一」 | 少一层就 404 |
| 前缀在**哪一层加**是设计选择 | 本章把 `/api` 放 main、`/v1` 放汇总、资源名放资源文件 |
| 分层的好处 | 换网关前缀只改 `config.api_prefix` |

### 2.2 tags 叠加而非覆盖

实测 OpenAPI：

```text
/api/v1/items   -> ["商品"]
/api/v1/users   -> ["用户"]
/health         -> ["运维"]
```

| 场景 | 结果 | 依据 |
| --- | --- | --- |
| 只有子 router 有 tags | 保留子 router 的 | `[P3]` |
| 父级 include 时也给 tags | 两者**合并**成列表 | `[P3]` |
| 都没有 tags | OpenAPI 里是 `null`（不是空列表） | 第 04 章实测（见 03 章 4.x） |

### 2.3 应用工厂

```python
def create_app() -> FastAPI:
    application = FastAPI(...)
    application.include_router(api_router, prefix=settings.api_prefix)
    return application

app = create_app()
```

实测：

```text
create_app() 返回不同实例：True，路由数 6/6
```

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 测试隔离 | 每个测试造一个干净 app，不受前一个测试的 `dependency_overrides` 污染 | `[P4]` |
| 多配置 | 同一套代码用不同 Settings 起多个实例 | `[P4]` |
| 延迟导入 | 只有调用时才装配，减少 import 期副作用 | `[P1]` |

> 注意：工厂函数**不是** ASGI 应用。要么像本章一样额外暴露模块级 `app = create_app()`，要么用 `uvicorn shop.main:create_app --factory`。忘了这一步会报「'function' object is not callable」类的错误。

## 3. API 逐一拆解

### 3.1 `APIRouter(...)` 参数

| 参数 | 类型 | 默认 | 作用 | 注意 | 依据 |
| --- | --- | --- | --- | --- | --- |
| `prefix` | `str` | `""` | 路径前缀 | 不以 `/` 结尾、不含 `{param}` | `[P3]` |
| `tags` | `list[str \| Enum]` | `None` | 文档分组 | 与父级叠加 | `[P3]` |
| `dependencies` | `Sequence[Depends]` | `None` | 组内统一依赖 | 第 39 章 | `[P3]` |
| `responses` | `dict` | `None` | 组内统一响应文档 | 第 26 章 | `[P3]` |
| `default_response_class` | `type[Response]` | 继承 | 默认响应类 | — | `[P3]` |
| `deprecated` | `bool` | `None` | 整组标记废弃 | — | `[P3]` |
| `include_in_schema` | `bool` | `True` | 整组不进文档 | — | `[P3]` |

### 3.2 `include_router(...)` 参数

| 参数 | 作用 | 注意 |
| --- | --- | --- |
| `router` | 要挂载的 router | 必填 |
| `prefix` | 追加前缀 | 与 router 自身 prefix 拼接 |
| `tags` | 追加 tags | 合并 |
| `dependencies` | 追加依赖 | 合并 |
| `responses` | 追加响应文档 | 合并 |
| `include_in_schema` | 是否进文档 | — |

### 3.3 前缀写在哪一层

| 方案 | `/api` 位置 | `/v1` 位置 | 资源名位置 | 适用 |
| --- | --- | --- | --- | --- |
| A（本章） | main | 汇总 router | 资源 router | 多版本并存 |
| B | main | main | 资源 router | 单版本小项目 |
| C | 网关 | 汇总 router | 资源 router | `/api` 由 Nginx 剥离 |

> 注意：方案 C 要配合 `--root-path`（第 54 章），否则 OpenAPI 里的 `servers` 与实际访问地址不一致。

## 4. 边界条件

### 4.1 空前缀与 `/`

实测：

```text
@router.get("")   → /api/v1/items       200
@router.get("/")  → /api/v1/items/      200（但访问无斜杠版会 307）
带尾斜杠请求       → 307 -> http://testserver/api/v1/items
```

| 写法 | 拼出的路径 | 建议 |
| --- | --- | --- |
| `@router.get("")` | `/api/v1/items` | ✅ 推荐 |
| `@router.get("/")` | `/api/v1/items/` | ⚠️ 会引发 307 |
| 两者同时注册 | 两条路径共存 | ❌ 不要 |

第 03 章实测过：`""` 和 `"/"` 可以同时注册，`/x` 命中 `""`、`/x/` 命中 `"/"`，**无重定向**。但混用会让前端困惑。

### 4.2 prefix 的硬约束

| 写法 | 结果 |
| --- | --- |
| `prefix="/items"` | ✅ |
| `prefix="items"` | ❌ 启动报错 |
| `prefix="/items/"` | ⚠️ 拼出 `//` |
| `prefix="/items/{item_id}"` | ❌ 不允许参数 |

### 4.3 循环导入

典型场景：

```python
# a.py
from .b import helper      # ← 需要 b

# b.py
from .a import Router      # ← 又需要 a
```

```text
ImportError: cannot import name 'X' from partially initialized module 'a'
（most likely due to a circular import）
```

| 解法 | 做法 | 适用 | 依据 |
| --- | --- | --- | --- |
| 1. 下移到函数内 | 在函数体里 `from .b import helper` | 调用时才需要 | `[P1]` |
| 2. 只导入模块不导入名字 | `from . import b` 然后 `b.helper()` | 需要互相引用 | `[P1]` |
| 3. 抽第三方模块 | 把共用部分放 `core/`，双方都依赖它 | 结构性解法（推荐） | `[P1]` |

> 注意：`TYPE_CHECKING` + 字符串注解（`from __future__ import annotations`）只解决**类型标注**的循环，不能解决运行期依赖。

### 4.4 `src/` 布局

```text
project/
├── src/
│   └── shop/
│       ├── __init__.py
│       └── main.py
├── tests/
└── pyproject.toml
```

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 防止「误把仓库根当包」 | 不用 `src/` 时，根目录下的 `utils/` 可能和别处的同名包冲突 | `[P6]` |
| 与打包工具一致 | `uv_build`/hatchling 默认支持 `src/` | `py-base/29` |
| 测试更干净 | 必须安装（或 `pip install -e .`）才能导入，暴露漏配的依赖 | `[P6]` |

启动命令随之变化：

```powershell
uv run uvicorn shop.main:app --reload --app-dir src
```

### 4.5 `__init__.py` 要不要写

| 情况 | 行为 | 依据 |
| --- | --- | --- |
| 有 `__init__.py` | 普通包，可放 `__version__` | `[P1]` |
| 没有（Python 3.3+） | 命名空间包，多数情况能导入 | `[P5]` |
| 用 mypy/ruff/打包工具 | 常要求显式 `__init__.py` | `[P6]` |

> 注意：本章示例全部写了 `__init__.py`，不是因为它「必需」，而是因为它「更可控」。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `prefix="/items/"` | 路径出现 `//` | 不带尾斜杠 | `[P3]` |
| `include_router(r, prefix="/api/")` | 同上 | 不带尾斜杠 | `[P3]` |
| `prefix="items"` | 启动报错 | 前导 `/` | `[P3]` |
| prefix 里写 `{id}` | 启动报错 | 参数写在接口上 | `[P3]` |
| `@router.get("/")` 当集合接口 | 307 重定向 | `@router.get("")` | 实测 |
| `""` 与 `"/"` 混用 | 两个路径共存，前端困惑 | 统一 `""` | 实测 |
| 直接 `python api/v1/items.py` | 相对导入报错 | `uvicorn shop.main:app` | `[P1]` |
| 相对导入跨两层以上 | `...` 难读易错 | 用绝对导入 | `[P1]` |
| 忘记 `__init__.py` | 打包/mypy 异常 | 显式创建 | `[P6]` |
| 在 `__init__.py` 里 import main | 循环导入 | `__init__.py` 保持空或只放版本号 | `[P1]` |
| 模块互相 import | partially initialized | 三种解法见 4.3 | `[P1]` |
| 在 import 期连数据库 | 测试也会连、启动变慢 | 放 `lifespan` | 第 67 章 |
| 在 import 期读配置就报错 | CI 无法 import | 配置给默认值 | 第 66 章 |
| 所有接口写 `main.py` | 文件膨胀、协作冲突 | 一资源一文件 | `[P7]` |
| 所有资源写在 `router.py` | 变回大文件 | `router.py` 只做聚合 | `[P7]` |
| `router.py` 里写业务逻辑 | 职责混乱 | 只 include | `[P7]` |
| 不区分版本目录 | 将来 v2 只能改老接口 | `api/v1/` | `[P7]` |
| 版本前缀写在资源 router 里 | 每个资源都要重复写 | 放汇总层 | `[P7]` |
| tags 写成 `["items"]` 英文 | 文档中英混杂 | 统一中文或统一英文 | `[P3]` |
| 忘记给 router 加 tags | OpenAPI 里 `null` | 统一加 | 实测 |
| 用 `include_router` 重复挂同一 router | 路由翻倍 | 自查 `routes` | 第 03 章 |
| 先 include 通配 router | 精确路由被吃 | 精确 router 先 include | 第 03 章 |
| 工厂函数不暴露 `app` | uvicorn 找不到 | `app = create_app()` 或 `--factory` | `[P4]` |
| 在工厂里读环境变量但不给默认 | 启动即崩 | 给默认值 | 第 66 章 |
| `src/` 布局忘了 `--app-dir` | `Could not import module` | `--app-dir src` | `[P6]` |
| 用 `from shop import *` | 命名污染 | 显式导入 | `[P8]` |
| 模块名与标准库同名（`types.py`） | 覆盖标准库 | 换名 | `[P1]` |
| 模块名与第三方库同名（`fastapi.py`） | 循环/覆盖导入 | 换名 | `[P1]` |
| 目录名含 `-`（`my-app/`） | 无法 import | 用 `_` | `[P1]` |
| 目录名含中文 | 部分工具链异常 | 用英文 | `[P1]` |
| 用 `sys.path.append` 硬改路径 | 环境差异、CI 崩 | 正确布局 + `--app-dir` | `[P2]` |
| 把 `tests/` 放进包内 | 打包进产物 | 放包外 | `py-base/29` |
| 配置散落各模块 | 换环境全局搜索 | `core/config.py` | 第 66 章 |
| 依赖 `include` 顺序但没注释 | 后人改动踩坑 | 注释说明顺序原因 | 第 03 章 |

## 6. 最佳实践与编码建议

**推荐目录模板（50 接口以内够用）**：

```text
shop/
├── main.py                 ← 装配：create_app() + app
├── core/
│   ├── config.py           ← Settings
│   ├── errors.py           ← 统一错误（第 34 章）
│   └── security.py         ← 鉴权（第 46 章）
├── api/
│   └── v1/
│       ├── router.py       ← 只 include
│       ├── items.py        ← 一资源一文件
│       └── users.py
├── models/                 ← Pydantic 模型（第 13 章）
└── services/               ← 业务逻辑（第 56 章）
```

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| `main.py` 只做装配 | 一眼看懂应用由哪些模块组成 | `[P7]` |
| `router.py` 只做聚合 | 新增资源只改一处 | `[P7]` |
| 一资源一文件 | 减少合并冲突 | `[P7]` |
| 前缀分层加 | `/api` 在 main、`/v1` 在汇总 | `[P7]` |
| 用应用工厂 | 测试隔离 | `[P4]` |
| `__init__.py` 保持空 | 避免 import 副作用 | `[P1]` |
| 导入优先用绝对路径 | 可读、可搜索 | `[P1]` |
| 循环依赖用「抽第三方模块」解 | 结构性解决 | `[P1]` |
| 路径全小写复数 | `/items` 而非 `/item` | `[P7]` |
| 健康检查放 main | 不版本化 | 第 03 章 |

**自查命令**：

```powershell
# 打印完整路由表（含前缀）
uv run python -c "from shop.main import app; [print(f'{r.path:30} {sorted(getattr(r,\"methods\",[]) or [])}') for r in app.routes]"
```

**边界**：

- 本章的 `ITEMS`/`USERS` 是模块级字典，多进程不共享（第 02 章 2.5）。
- 本章 `config.py` 用手写 `dataclass`，第 66 章会换成 `pydantic-settings`（带类型校验与 `.env` 支持）。
- `api/v1/router.py` 用相对导入，`main.py` 用绝对导入——这是刻意对照，两种都能跑。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[P1]` | 官方文档 | https://docs.python.org/3/tutorial/modules.html | 模块/包/导入机制、循环导入 |
| `[P2]` | 官方文档 | https://docs.python.org/3/library/sys.html#sys.path | `sys.path` 查找顺序 |
| `[P3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/bigger-applications/ | `APIRouter`、`include_router`、prefix 与 tags |
| `[P4]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/testing-dependencies/ | 应用工厂与测试隔离 |
| `[P5]` | 规范 | https://peps.python.org/pep-0420/ | 命名空间包 |
| `[P6]` | 官方文档 | https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ | `src/` 布局 |
| `[P7]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/bigger-applications/ | 项目结构最佳实践 |
| `[P8]` | 规范 | https://peps.python.org/pep-0008/#imports | 导入规范 |

> **核对状态**：`[P1]`–`[P8]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 FastAPI 0.146.0 / Python 3.12.8 输出，`examples/verify.py` 可复现 10/10 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 模块与包的区别
- [ ] `shop.main:app` 的两部分各是什么
- [ ] `include_router` 的四步动作
- [ ] 三层前缀分别写在哪一层、为什么这样分
- [ ] tags 是叠加还是覆盖
- [ ] 循环导入为什么会发生、三种解法

**能写出（代码层）**：

- [ ] 一套 5 文件的骨架（main/router/资源×2/config）
- [ ] `create_app()` 工厂 + 模块级 `app`
- [ ] 相对导入与绝对导入两种写法
- [ ] `--app-dir` 启动 `src/` 布局

**能判断（避坑层）**：

- [ ] 看到 `prefix="/items/"` 能指出 `//`
- [ ] 看到 `@router.get("/")` 能指出 307
- [ ] 看到 `python items.py` 能指出相对导入错误
- [ ] 看到 `partially initialized module` 能定位循环导入
- [ ] 看到只有 `create_app` 没有 `app` 能指出 uvicorn 找不到

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] `uv run uvicorn shop.main:app --reload` 启动成功
- [ ] 新增一个资源只需改两个文件

## 9. 下一章衔接

第 05 章 `路径参数`：进入 M01，开始讲「数据怎么从 URL 进来」。会讲清路径参数的类型转换、`/items/1` 与 `/items/abc` 的差异、路径参数与查询参数的边界、`Path()` 校验的前置知识。

本章留下的伏笔：

1. `config.py` 里的配置对象——第 66 章换成 `pydantic-settings`。
2. `dependencies` 参数还没用——第 39 章讲全局/组内依赖。
3. `models/` 与 `services/` 目录还没建——第 13、56 章补齐。
