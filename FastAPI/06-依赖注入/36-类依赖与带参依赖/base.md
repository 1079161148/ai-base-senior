# 36 类依赖与带参依赖 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「`Depends` 拿到一个对象时到底怎么判断、类与实例的语义差异、配置怎么焊死、状态放哪」拆开。学完这章，你要能一眼看出一个 `Depends(X)` 会注入什么，以及它的参数会不会出现在 API 文档里。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 35 章（`Depends` 基础） |
| 覆盖范围 | 类依赖、`__call__`、实例依赖、工厂闭包、配置与 OpenAPI 的关系、实例状态 |
| 明确不覆盖 | 子依赖缓存（第 37 章）、`Annotated` 别名（第 38 章）、依赖覆盖（第 41 章）|
| 学完验收 | 能跑通 `verify.py` 13/13、能预测三种写法的 OpenAPI、能解释类 vs 实例 |

## 0. 怎么用这份文件

**依据约定**：`` `[Cn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 依赖是「可调用 + 签名」两件事
2 机制（第 2 节）    → 类/实例/闭包三条分支
3 API（第 3 节）     → 三种写法与参数来源
4 边界（第 4 节）    → 状态、并发、OpenAPI、继承
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 该用哪种
```

## 1. 概念：依赖 = 可调用 + 可解析签名

`Depends(X)` 做两件事：

1. 把 `X` 的「调用签名」交给依赖解析器（决定 query/header/body 参数）；
2. 在请求时调用它，把返回值注入端点。

| X 是什么 | 签名从哪来 | 调用什么 | 注入什么 |
| --- | --- | --- | --- |
| 函数 | 函数签名 | 函数 | 返回值 |
| 类 | `__init__` | 构造 | **实例** |
| 实例 | `__call__` | `__call__` | 返回值 |
| 闭包 | 内层函数签名 | 内层函数 | 返回值 |

## 2. 机制：三条分支

```text
Depends(X)
 → inspect.iscoroutinefunction(X) / iscoroutinefunction(X.__call__)
 → 取签名：
      X 是类        → inspect.signature(X.__init__)（去掉 self）
      X 是实例/函数 → inspect.signature(X)
 → 解析每个参数为 query/header/path/body
 → 调用：类 → X(**kwargs)；实例 → X.__call__(**kwargs)
```

| 事实 | 说明 |
| --- | --- |
| 类作依赖注入实例 | 实测：注解写 `dict` → 500（`ResponseValidationError`）|
| 实例作依赖调 `__call__` | `__init__` 参数完全不解析（实测 OpenAPI 无参数）|
| `__call__(self, request)` | `request` 由框架注入，不暴露给客户端 |
| 闭包工厂 | 只有内层签名进 OpenAPI，外层配置被捕获 |

### 实测对照

| 端点 | 依赖写法 | OpenAPI 参数 |
| --- | --- | --- |
| `/fixed/small` | `Depends(FixedPage(3))` | `[]` |
| `/fixed/class` | `Depends(ConfigurablePage)` | `["size"]` |
| `/items` | `Depends()` + 注解 `CommonQueryParams` | `["q","skip","limit"]` |
| `/limited` | `Depends(limiter)` | `[]` |

## 3. API 逐个拆解

### 3.1 类依赖

```python
class CommonQueryParams:
    def __init__(self, q: str | None = None, limit: int = 10) -> None:
        ...

@app.get("/items")
def items(c: Annotated[CommonQueryParams, Depends()]) -> dict: ...
```

| 要点 | 说明 |
| --- | --- |
| `Depends()` 无参 | 从注解推断类 |
| 等价 `Depends(CommonQueryParams)` | 二选一 |
| 端点里用属性 | `c.limit` |
| 需要 dict 输出 | 自己转，别直接 `return c` |

### 3.2 实例依赖

```python
class FixedPage:
    def __init__(self, size: int) -> None:
        self.size = size

    def __call__(self) -> dict[str, int]:
        return {"size": self.size}

SMALL = FixedPage(3)

@app.get("/fixed/small")
def small(page: Annotated[dict[str, int], Depends(SMALL)]) -> dict: ...
```

| 要点 | 说明 |
| --- | --- |
| 配置在构造时固定 | 想改只能换实例 |
| `__call__` 的签名决定参数 | 本例无参数 → OpenAPI 空 |
| 适合限流器/缓存/客户端 | 有状态对象 |

### 3.3 工厂闭包

```python
def require_header(name: str, expected: str = "ok"):
    def dependency(value: Annotated[str | None, Header(alias=name)] = None) -> str:
        ...
    return dependency

Depends(require_header("X-Api-Key"))
```

| 要点 | 说明 |
| --- | --- |
| 配置值不进 OpenAPI | 实测：`expected`/`ok` 不出现 |
| 每个端点只暴露自己的头 | `/factory/a` → `X-Api-Key` |
| Header alias 大小写 | OpenAPI 保留 `X-Api-Key`（实测）|

### 3.4 参数来源决定注入点

| 声明 | 进 OpenAPI 的位置 |
| --- | --- |
| `Query(...)` | `parameters[in=query]` |
| `Header(...)` | `parameters[in=header]` |
| `Path(...)` | `parameters[in=path]` |
| Pydantic 模型 | `requestBody` |
| `Request` / `Response` | 不出现 |
| `Depends(...)` | 递归展开 |

## 4. 边界条件

### 4.1 类 vs 实例语义（实测）

```python
class Cls:
    def __init__(self) -> None:
        self.tag = "instance-of-class"

    def __call__(self) -> dict:
        return {"tag": "call-result"}
```

| 写法 | 注入 |
| --- | --- |
| `Depends(Cls)` | `Cls()` 实例 → `tag == "instance-of-class"` |
| `Depends(Cls())` | `{"tag": "call-result"}` |

这是本章最容易翻车的地方：写 `Depends(Cls)` 却按 `__call__` 返回值使用 → 500。

### 4.2 实例状态与并发

限流器把计数放在 `self.calls`：

| 风险 | 说明 |
| --- | --- |
| 多 worker | 每个进程一份计数（实测环境单进程，未验证多进程）|
| 多线程 | dict 操作原子性够用，但逻辑非原子 |
| 内存增长 | key 永不清理 → 需 TTL |
| 测试污染 | 需要 `reset()` |

生产建议：Redis + 滑动窗口。

### 4.3 类依赖里的继承

`Depends(Cls)` 会解析 `__init__`；若子类覆盖 `__init__`，只解析子类签名。父类新增必填参数会影响子类 —— 需要显式传默认值。

### 4.4 类依赖 VS Pydantic 模型

| | 类依赖 | Pydantic 模型 |
| --- | --- | --- |
| 用途 | 解析 + 逻辑 | 纯数据校验 |
| 位置 | query/header/path 等 | 默认 body |
| 返回值 | 实例（任意行为）| 模型实例（纯数据）|
| 建议 | 需要行为时用 | 需要校验时用 |

### 4.5 工厂闭包与缓存

每次 `Depends(require_header(...))` 都会新建闭包；同一请求内多次 `Depends` **同一闭包对象**才共享缓存。写成两行两条 `Depends(require_header("X"))` 是**两个**依赖，会执行两次（第 37 章细讲）。

### 4.6 `__call__` 是 async 的情况

`async def __call__` 可用；框架会 `await`。判断依据是实现细节，**未实测** async `__call__`，用前验证。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `Depends(Cls)` 当 dict 用 | 500 `ResponseValidationError` | 用属性 | 实测 |
| 以为类依赖会调 `__call__` | 拿到实例 | 实例作依赖 | 实测 |
| 实例依赖想改配置 | 改不动 | 用类/工厂 | `[C1]` |
| 类依赖传配置期望固定 | 配置变 query 参数 | 用实例 | 实测 |
| 限流器用模块级 dict | 多 app 串数据 | 实例属性 | `[C3]` |
| 限流器多进程 | 每 worker 独立计数 | Redis | `[C3]` |
| 计数器不清理 | 内存泄漏 | TTL/LRU | `[C3]` |
| 工厂里做重 IO | 每次建依赖都执行 | 移到内层/服务层 | `[C1]` |
| `Depends(lambda: ...)` 返回大对象 | 每请求构造 | 轻量返回 | `[C2]` |
| 类 `__init__` 里查库 | 每请求一次 | 用子依赖+缓存 | 第 37 章 |
| 局部类 + 注解 | 注解解析失败 | 类放模块级 | `[C2]` |
| 忽略 Header alias 大小写 | 断言失败 | 按原样断言 | 实测 |
| 依赖里返回 ORM 对象 | 响应模型校验失败 | 转 DTO | 第 21 章 |
| 用类依赖做纯数据校验 | 行为与模型混淆 | 用 Pydantic | `[C1]` |
| 工厂配置写进 OpenAPI 期望 | 实际不出现 | 显式参数 | 实测 |
| 实例依赖跨请求复用未考虑线程安全 | 偶发数据错乱 | 加锁/无状态 | `[C3]` |
| `Depends()` 与注解类型不一致 | 定义期/运行期错 | 保证一致 | `[C1]` |
| 把类依赖当中间件 | 执行时机不同 | 明确边界 | 第 39 章 |
| 类 `__init__` 参数用 `Body` | 变成请求体，文档结构意外 | 明确参数来源 | `[C1]` |

## 6. 最佳实践与编码建议

### 6.1 该用哪种

| 场景 | 选择 |
| --- | --- |
| 纯参数整理 | 函数（第 35 章）|
| 需要属性访问 | 类 |
| 需要固定配置 | 实例 |
| 同构多配置 | 工厂 |
| 需要清理资源 | `yield`（第 40 章）|

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 类依赖只存数据 | 逻辑放方法/服务层 |
| 实例依赖保持无状态或显式加锁 | 并发安全 |
| 工厂返回闭包，不返回对象 | 签名清晰 |
| 配置项不进 OpenAPI 时写注释 | 团队不困惑 |
| 限流器提供 `reset()` | 便于测试 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 分页对象 | 类依赖 |
| 限流 | 实例 + `__call__` |
| 多租户 key | 工厂 |
| 单例客户端 | 实例（注意线程安全）|
| 依赖套依赖 | 第 37 章 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[C1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/classes-as-dependencies/ | 类作依赖 |
| `[C2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/ | `Depends` 与可调用对象 |
| `[C3]` | 参考 | https://redis.io/docs/latest/develop/use/patterns/distributed-locks/ | 分布式限流思路 |

> **核对状态**：`[C1]`–`[C3]` 为官方/参考链接，**本次未逐页直连复核**；类注入实例、实例调 `__call__`、OpenAPI 参数差异、Header alias 大小写、限流 429、工厂配置不入文档均为本机实测，`examples/verify.py` 复现 13/13 通过。async `__call__`、多进程限流**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三种写法的注入差异
- [ ] `__init__` 与 `__call__` 哪个进 OpenAPI
- [ ] 为什么实例依赖配置固定
- [ ] 工厂闭包为什么能藏配置
- [ ] 实例状态在并发下的风险

**能写出（代码层）**：

- [ ] 类依赖 + 属性访问
- [ ] 实例限流器 + `Retry-After`
- [ ] 工厂生成两个不同头的依赖
- [ ] 工厂截断 `limit`
- [ ] `lambda` 依赖

**能判断（避坑层）**：

- [ ] 看到 `Depends(Cls)` 当 dict 用 → 指出 500
- [ ] 看到实例依赖想传配置 → 指出改不动
- [ ] 看到限流器用全局变量 → 指出串数据
- [ ] 看到多进程限流 → 指出不准
- [ ] 看到工厂重复构造 → 指出缓存边界

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 13/13
- [ ] `/docs` 对比 `/fixed/small` 与 `/fixed/class`
- [ ] 连续请求 `/limited` 看 429

## 9. 下一章衔接

第 37 章 `子依赖与缓存`：依赖套依赖（用户 → 权限 → 角色）、同一请求内的结果缓存、`use_cache=False` 强制重算、缓存与 `yield` 的交互。

本章留下的伏笔：

1. 依赖链与缓存语义在 第 37 章。
2. 别名复用 第 38 章。
3. 全局依赖 第 39 章。
4. 会话清理 第 40 章。