# 37 子依赖与缓存 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「依赖树怎么遍历、缓存怎么判定命中、`use_cache=False` 影响谁、异常如何截断、缓存与 `yield` 怎么交互」拆开。学完这章，你要能预测任意依赖树的执行次数与顺序。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0（本机实测） |
| 前置 | 第 35–36 章（`Depends`、类依赖） |
| 覆盖范围 | 依赖树、执行顺序、单请求缓存、`use_cache=False`、缓存 key、异常截断 |
| 明确不覆盖 | 跨进程缓存、`yield` 清理细节（第 40 章）、`Annotated` 别名（第 38 章）|
| 学完验收 | 能跑通 `verify.py` 12/12、能预测执行序列、能解释缓存 key |

## 0. 怎么用这份文件

**依据约定**：`` `[Sn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 依赖树
2 机制（第 2 节）    → 遍历 + 缓存表
3 API（第 3 节）     → use_cache 与声明方式
4 边界（第 4 节）    → 顺序、异常、yield、闭包
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 分层鉴权模板
```

## 1. 概念：依赖树而不是依赖列表

```text
/admin
├─ require_role
│  └─ get_permissions
│     └─ get_user
└─ get_user（已缓存）
```

| 术语 | 含义 |
| --- | --- |
| 叶子依赖 | 不依赖别人（`get_user`）|
| 中间依赖 | 依赖叶子（`get_permissions`）|
| 根依赖 | 端点直接使用的（`require_role`）|
| 共享节点 | 多处引用（`get_user`）→ 命中缓存 |

## 2. 机制：遍历 + 缓存表

```text
solve_dependencies(dependant, request, cache=dict())
  for sub in dependant.dependencies:
      if sub.cache_key in cache and sub.use_cache:
          value = cache[sub.cache_key]          # 命中
      else:
          kwargs = solve_dependencies(sub, ...) # 递归（深度优先）
          value = call(sub.call, **kwargs)
          cache[sub.cache_key] = value          # 写入
```

| 事实 | 说明 |
| --- | --- |
| 深度优先 | 先子后父（实测 `user → perms → role`）|
| 缓存 key | 依赖的 `cache_key`，本质是「可调用对象 + 参数」的标识 |
| 缓存生命周期 | 单次请求的 `cache` 字典 |
| 端点自身参数 | 最后解析 |

### 实测：顺序与次数

| 请求 | `CALL_LOG` |
| --- | --- |
| `/order?scope=read&role=user` | `["user", "perms", "role"]` |
| `/admin?scope=write&role=admin` | `["user", "perms", "role"]`（`user` 只 1 次）|
| `/nocache` | `["user", "user"]` |

## 3. API 逐个拆解

### 3.1 声明子依赖

```python
def get_permissions(user: Annotated[dict, Depends(get_user)]) -> dict: ...
```

依赖函数的参数与端点同权，所以能直接 `Depends`。

### 3.2 `use_cache`

| 写法 | 效果 |
| --- | --- |
| `Depends(fn)` | 默认 `use_cache=True` |
| `Depends(fn, use_cache=False)` | 该处重算 |
| 同一函数两处：一处 True 一处 False | True 处用缓存（若已算过），False 处重算 |

实测 `/nocache`：`cached` 走缓存、`fresh` 重算 → `["user", "user"]`。

注意：`use_cache=False` 只影响**该引用点**，不会把缓存表清空；其他引用点仍可能命中之前的值。

### 3.3 参数化依赖与缓存

```python
Depends(get_user)          # key 含「无参数」
Depends(make_dep("a"))     # 每次调用 make_dep 生成新对象 → 不同 key
```

同一请求内如果两次都写 `Depends(make_dep("a"))`，会得到**两个闭包对象**，因此各执行一次。想让它们共享，先赋值给变量：

```python
NEED_A = make_dep("a")

def endpoint(x: Annotated[..., Depends(NEED_A)], y: Annotated[..., Depends(NEED_A)]): ...
```

## 4. 边界条件

### 4.1 异常截断（实测）

| 抛错位置 | `CALL_LOG` | 状态码 |
| --- | --- | --- |
| `get_user` 缺头 | `["user"]` | 401 |
| `get_user` 用户不存在 | `["user"]` | 404 |
| `get_permissions` 权限不足 | `["user", "perms"]` | 403 |
| `require_role` 角色不符 | `["user", "perms", "role"]` | 403 |

结论：抛错即中断，父依赖不执行，端点不执行。

### 4.2 缓存不跨请求（实测）

两次 `/count` → `user` 调用数 1 → 2。

### 4.3 缓存与 `yield`

`yield` 依赖在同一请求内也只创建一次、共享同一对象（实测 `r1 is r2 == True`）。清理发生在请求结束（第 40 章）。

### 4.4 缓存与可变对象

依赖返回 dict/list 时，同一请求内多个使用方拿到的是**同一个对象**。修改它会互相影响。建议返回不可变结构（tuple/frozen dataclass）或在依赖内拷贝。

### 4.5 OpenAPI 去重（实测）

`X-User` 被 `get_user` 声明一次、被端点间接引用多次 → `parameters` 里只出现 1 次。

### 4.6 依赖树深度

| 深度 | 影响 |
| --- | --- |
| 2–3 层 | 推荐（认证 → 权限 → 角色）|
| 5 层以上 | 难排障，考虑合并 |
| 交叉引用 | 缓存救场，但可读性差 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 以为依赖全局只跑一次 | 每请求都跑 | 缓存是单请求 | 实测 |
| 在不同参数下期望不同结果 | 命中缓存 | `use_cache=False` | 实测 |
| 每次 `Depends(make_dep(x))` | 新闭包 → 不共享 | 提前赋值复用 | 实测 |
| 依赖返回可变对象并修改 | 同请求内互相影响 | 返回副本/只读 | `[S2]` |
| 依赖里查库又在多层重复写 | 以为 N 次，实际 1 次 | 明确缓存语义 | `[S1]` |
| 用依赖缓存当业务缓存 | 跨请求失效 | Redis | `[S3]` |
| `yield` 依赖退出后继续用 | 资源已关闭 | 作用域内使用 | 第 40 章 |
| 深层依赖里做重 IO | 首请求慢 | 异步/缓存 | `[S3]` |
| 依赖树交叉引用无注释 | 难排障 | 注释依赖意图 | `[S1]` |
| 依赖里写全局计数器 | 并发/串请求 | 用日志/trace | `[S2]` |
| 依赖抛 `HTTPException` 后还想兜底 | 已中断 | 处理在依赖内 | 第 31 章 |
| 用 `use_cache=False` 到处关 | IO 放大 | 只在该处开 | 实测 |
| 忽略 OpenAPI 参数去重 | 断言失败 | 按去重后断言 | 实测 |
| `Depends` 同一函数不同注解 | 定义期可能冲突 | 统一注解 | `[S1]` |
| 依赖返回 ORM 对象 | 响应校验失败 | DTO | 第 21 章 |
| 缓存依赖返回大对象 | 每请求一份 | 只返回必要字段 | `[S3]` |
| 依赖树顶层做鉴权却返回 500 | 未用 `HTTPException` | 用 401/403 | 第 31 章 |
| 拿缓存结果做时间敏感判断 | 值过期感 | 关缓存 | 实测 |
| 依赖树共享对象被并发修改 | 数据竞争 | 不可变/加锁 | `[S2]` |

## 6. 最佳实践与编码建议

### 6.1 分层鉴权模板

```python
# 1) 认证：只认 token，失败 401
def get_user(authorization: Annotated[str | None, Header()] = None) -> User: ...


# 2) 授权：依赖用户，失败 403
def require_scopes(
    user: Annotated[User, Depends(get_user)],
    required: Annotated[list[str], Query()] = [],
) -> User: ...


# 3) 端点
@app.get("/admin")
def admin(user: Annotated[User, Depends(require_scopes)]) -> dict: ...
```

`get_user` 只在 1 层解析；`require_scopes` 复用。

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 叶子依赖无副作用 | 便于缓存复用 |
| 返回冻结结构 | 避免跨使用者污染 |
| 少用 `use_cache=False` | IO 放大 |
| 工厂依赖提前实例化 | 共享缓存 |
| 依赖层级别超过 4 层就拆 | 可维护性 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 复用认证 | 叶子依赖 |
| 权限检查 | 中间依赖 |
| 需要最新值 | `use_cache=False` |
| 跨请求缓存 | Redis |
| 请求内共享状态 | `request.state` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[S1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/sub-dependencies/ | 子依赖与缓存 |
| `[S2]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/ | 高级用法（缓存/作用域）|
| `[S3]` | 参考 | https://redis.io/docs/latest/develop/use/patterns/ | 跨进程缓存思路 |

> **核对状态**：`[S1]`–`[S3]` 为官方/参考链接，**本次未逐页直连复核**；执行顺序、单请求缓存、`use_cache=False`、跨请求不缓存、异常截断、OpenAPI 去重、`yield` 同对象均为本机实测，`examples/verify.py` 复现 12/12 通过。缓存 key 的内部实现细节**未逐行核对**，结论来自行为观测。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 依赖树的遍历顺序
- [ ] 缓存的 key 与生命周期
- [ ] `use_cache=False` 影响范围
- [ ] 异常在哪一层截断
- [ ] 缓存与 `yield` 的关系

**能写出（代码层）**：

- [ ] 三层鉴权链
- [ ] 显式 `use_cache=False`
- [ ] 复用同一闭包对象
- [ ] 请求内共享状态（`request.state`）

**能判断（避坑层）**：

- [ ] 看到依赖写全局计数器 → 指出并发问题
- [ ] 看到 `make_dep()` 写两次 → 指出不共享缓存
- [ ] 看到依赖返回可变对象被改 → 指出污染
- [ ] 看到到处 `use_cache=False` → 指出 IO 放大
- [ ] 看到依赖树 6 层 → 指出拆分

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `/order` 看 `CALL_LOG`
- [ ] `/nocache` 看 2 次调用

## 9. 下一章衔接

第 38 章 `Annotated 共享依赖`：用 `type XDep = Annotated[...]` 把「类型 + 依赖」打包成别名，全项目复用，避免每个函数重复写 `Depends(...)`，并讨论别名的类型检查收益。

本章留下的伏笔：

1. 别名复用 第 38 章。
2. 全局依赖 第 39 章。
3. `yield` 清理 第 40 章。
4. 测试替换 第 41 章。