# 41 依赖覆盖 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「覆盖在哪一步生效、key 怎么匹配、为什么同名函数无效、测试怎么隔离、覆盖与 `yield` 怎么相处」拆开。学完这章，你要能安全地在测试里替换任何依赖。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0（本机实测） |
| 前置 | 第 35–40 章（`Depends`、缓存、`yield`） |
| 覆盖范围 | `dependency_overrides` 语义、key 匹配、嵌套覆盖、隔离、与 OpenAPI/缓存的关系 |
| 明确不覆盖 | pytest 插件生态、测试分层策略（第 71 章）|
| 学完验收 | 能跑通 `verify.py` 11/11、能写出隔离 fixture、能解释 key 匹配 |

## 0. 怎么用这份文件

**依据约定**：`` `[On]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 覆盖是什么
2 机制（第 2 节）    → 请求时查表
3 API（第 3 节）     → 增删清、替身写法
4 边界（第 4 节）    → key、嵌套、OpenAPI、缓存、yield
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ fixture 模板
```

## 1. 概念：覆盖是「运行时的依赖替换表」

| | 依赖覆盖 | 猴子补丁 |
| --- | --- | --- |
| 粒度 | 单个依赖 | 模块/全局 |
| 生效点 | 请求解析时 | 调用时 |
| 清理 | `clear()` | 手动还原 |
| 类型安全 | 靠自觉 | 差 |

`app.dependency_overrides: dict[Callable, Callable]`，就是一个普通字典。

## 2. 机制：请求时查表

```text
solve_dependencies(dependant)
  for sub in dependant.dependencies:
      call = app.dependency_overrides.get(sub.call, sub.call)
      value = call(**kwargs)
```

| 事实 | 说明 |
| --- | --- |
| 每次请求都查表 | 覆盖可随时增删 |
| 覆盖只换「调用目标」| 参数解析仍按**替身**签名 |
| 真实依赖完全不执行 | 实测 `REAL_CALLS == []` |
| 缓存按 `sub.call`（原 key）| 覆盖后缓存键不变 |

## 3. API 逐个拆解

### 3.1 增 / 删 / 清

```python
app.dependency_overrides[get_db] = fake_db
del app.dependency_overrides[get_db]
app.dependency_overrides.clear()
```

### 3.2 替身写法

| 真实依赖 | 替身要求 |
| --- | --- |
| `def dep() -> T` | 返回 T 即可 |
| `def dep() -> Iterator[T]` | 生成器或普通函数都可（实测）|
| `class Cls` | key 用 `Cls`，替身可以是任意 callable |
| 带参数依赖 | 替身自己的参数会被解析 |

### 3.3 覆盖鉴权

```python
app.dependency_overrides[require_token] = lambda: "test-token"
```

实测 `/me` 从 401 变 200。

## 4. 边界条件

### 4.1 key 是对象（实测）

```python
def get_db(): ...          # 模块里那个对象
def get_db(): ...          # 另一个同名函数 → 不同对象

app.dependency_overrides[get_db] = fake   # 不生效
```

结论：导入同一个对象再作 key。

### 4.2 嵌套（实测）

`get_config` 内部 `Depends(get_db)` → 覆盖 `get_db` 后 `get_config` 自动用替身。

### 4.3 类依赖（实测）

`Depends(Clock)` 的 key 是 `Clock`；覆盖成 `FakeClock` 后 `/now` 返回 `1999-01-01`。

### 4.4 OpenAPI（实测）

覆盖前后 `openapi.json` 完全相同。含义：**测试替身不会污染对外契约**。

### 4.5 替身参数（实测）

替身 `fake(y: int = Query(ge=1))` → `/q?y=5` 生效，`y=0` → 422。所以替身签名要写清楚，否则测试里的参数行为会变。

### 4.6 作用域（实测）

只在 `app.dependency_overrides` 上，其他 app 不受影响。

### 4.7 与 `yield` 的交互

替身是非生成器时，框架不会对替身做 `next()/close()`；实测可用。若替身也是生成器，清理照常。

### 4.8 与缓存

同请求内缓存键仍是原依赖对象；覆盖发生在调用前，因此缓存的是**替身结果**。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 同名字符串/函数作 key | 不生效（实测）| 用同一对象 | 实测 |
| 忘清理 | 污染后续测试 | fixture `finally: clear()` | `[O1]` |
| 生产环境保留覆盖 | 全站 fake | 只在测试 | `[O2]` |
| 替身签名与真实不一致 | 测试掩盖差异 | 保持接口 | `[O1]` |
| 以为会改 OpenAPI | 不会 | 别依赖 | 实测 |
| 覆盖父依赖却期望子依赖也换 | 不换（子依赖对象没被覆盖）| 覆盖真正被 `Depends` 的对象 | 实测 |
| 多处覆盖同一 key | 后者覆盖前者 | 集中管理 | `[O1]` |
| 覆盖后仍断言真实依赖被调用 | 期望错 | 断言 0 次 | 实测 |
| 用覆盖做功能开关 | 语义错 | 配置项 | `[O2]` |
| 替身里抛 `HTTPException` | 可测错误分支 | 合理使用 | `[O1]` |
| 覆盖 `yield` 依赖但替身不清理 | 资源语义不一致 | 保持生成器 | 第 40 章 |
| 在 `include_router` 前后覆盖有疑虑 | 按对象匹配，都生效 | 统一 fixture | 实测 |
| 覆盖后仍用真实类型注解 | 类型不符但运行 OK | 明确 Protocol | `[O2]` |
| 测试并发共享 app | 覆盖互相影响 | 每个测试新建 app | `[O1]` |
| 只测成功路径 | 覆盖分支没覆盖 | 正反各一条 | 第 71 章 |
| 覆盖多个 app 只清一个 | 残留 | 逐个清 | `[O1]` |
| 替身依赖第三方 IO | 测试变慢 | 纯内存 | `[O2]` |
| 把覆盖写进生产代码 | 意外替换 | 只在测试模块 | `[O2]` |
| 覆盖后不确认是否生效 | 测试仍走真实链路 | 断言真实依赖 0 次 | `[O1]` |

## 6. 最佳实践与编码建议

### 6.1 pytest fixture 模板

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: {"source": "fake-db"}
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
```

| 要点 | 说明 |
| --- | --- |
| `yield` + `finally` | 保证清理 |
| 每个 fixture 建新 client | 隔离 |
| 覆盖集中在 fixture | 可读 |

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 替身放在 `conftest.py` | 复用 |
| 替身保持最小 | 只实现用到的行为 |
| 覆盖 key 用导入的对象 | 防同名 |
| 断言「真实依赖 0 次」 | 确认覆盖生效 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 测试数据库 | 覆盖 `get_db` |
| 测试时间 | 覆盖 `Clock` |
| 免登录 | 覆盖 `require_token` |
| 模拟故障 | 替身抛异常 |
| 生产开关 | 配置项，不是覆盖 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[O1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/testing-dependencies/ | 依赖覆盖 |
| `[O2]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/testing-database/ | 测试数据库实践 |

> **核对状态**：`[O1]`–`[O2]` 为官方链接，**本次未逐页直连复核**；原依赖 0 次调用、嵌套自动替换、类依赖 key、同名函数无效、OpenAPI 不变、替身参数校验、作用域、非生成器替身均为本机实测，`examples/verify.py` 复现 11/11 通过。并发共享 app 的影响**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 覆盖表在哪一步生效
- [ ] key 的匹配规则
- [ ] 为什么 OpenAPI 不变
- [ ] 嵌套依赖如何被覆盖
- [ ] 覆盖与缓存的交互

**能写出（代码层）**：

- [ ] 覆盖函数/类依赖
- [ ] 覆盖鉴权
- [ ] fixture 清理
- [ ] 替身带参数
- [ ] 断言真实依赖 0 次

**能判断（避坑层）**：

- [ ] 看到同名函数 key → 指出无效
- [ ] 看到没清理 → 指出污染
- [ ] 看到生产代码里有覆盖 → 指出危险
- [ ] 看到替身签名差异大 → 指出掩盖 bug
- [ ] 看到指望覆盖改文档 → 指出不变

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] 手动改 `verify.py` 观察覆盖后 0 次调用
- [ ] `clear()` 后恢复

## 9. 下一章衔接

第 42 章 `实战：分页依赖`：`PageParams` + `Page[T]` 泛型响应模型，统一 `items/total/page/size` 结构，讲泛型模型与 `response_model` 的结合、`total` 从哪来、边界（空页、越界页码）。

本章留下的伏笔：

1. 分页结构 第 42 章。
2. 鉴权与多租户 第 43 章。
3. 测试策略 第 71 章。