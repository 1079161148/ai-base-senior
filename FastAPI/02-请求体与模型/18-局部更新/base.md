# 18 局部更新（PATCH）· 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「PATCH 与 PUT 的语义差别、`exclude_unset` 到底排除了什么、显式 null 怎么处理、并发覆盖怎么防」拆开。学完这章，你要能写出**不会误清空数据**的更新接口。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测；workspace 环境为 2.14.3，行为一致） |
| 前置 | 第 13–17 章（模型、约束、嵌套、特殊类型） |
| 覆盖范围 | PATCH 模型设计、`exclude_unset`/`exclude_none`、`model_fields_set`、404 与 422 分工、审计 |
| 明确不覆盖 | 乐观锁/ETag 的完整实现（第 87 行仅给思路）、数据库事务（M09）、批量更新（第 42 章） |
| 学完验收 | 能跑通 `verify.py` 10/10、能预测三种序列化参数的结果、能说清 null 的两种语义 |

## 0. 怎么用这份文件

**依据约定**：`` `[Pn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → PUT 与 PATCH 的语义差别
2 机制（第 2 节）    → fields_set 是怎么记录「传了什么」的
3 API（第 3 节）     → exclude_* 参数表
4 边界（第 4 节）    → 显式 null、空对象、嵌套、并发
5 注意事项（第 5 节）→ 20 条对照
6 最佳实践（第 6 节）→ 可直接抄的更新模板
```

## 1. 概念：PUT 替换 vs PATCH 合并

| 方法 | 语义 | 请求体必须包含 | 未出现的字段 |
| --- | --- | --- | --- |
| `PUT /products/1` | **整体替换** | 全部字段 | 被视为「要清空」 |
| `PATCH /products/1` | **局部合并** | 只传要改的 | 保持原值 |

现实中的接口几乎都需要 PATCH：客户端不总是拿得到完整对象（列表页只返回 id+name），强制全量提交会把未展示的字段清掉。

PATCH 的三条硬规则：

1. 模型字段**全部可选**；
2. 用 `exclude_unset=True` 取更新集；
3. 更新集为空也返回 200（幂等），不要报错。

## 2. 机制：`fields_set` 记录「用户到底给了什么」

```text
请求 JSON  {"name": "静音键盘"}
   ↓ Pydantic 解析
ProductPatch(name="静音键盘")            # 其余字段取默认 None
   ↓ 内部记录
model_fields_set = {"name"}              # 只有 name 被「显式赋值」
   ↓ model_dump(exclude_unset=True)
{"name": "静音键盘"}                      # 默认值不出现
```

三种情况对比（实测）：

| 请求 | `model_fields_set` | `exclude_unset` 输出 |
| --- | --- | --- |
| `{"name": "x"}` | `{"name"}` | `{"name": "x"}` |
| `{"note": null}` | `{"note"}` | `{"note": None}` |
| `{}` | `set()` | `{}` |
| 未构造（`ProductPatch()`） | `set()` | `{}` |

关键结论：**`null` 是「显式赋值」**，所以 `exclude_unset` 会保留它；只有 `exclude_none` 才会把它丢掉。

## 3. API 逐个拆解

### 3.1 三个序列化参数

| 参数 | 排除什么 | 适用场景 |
| --- | --- | --- |
| `exclude_unset=True` | 没被赋值过的字段 | PATCH 更新（标准写法） |
| `exclude_none=True` | 值为 `None` 的字段（含显式 null） | 「null 等于不改」的老系统兼容 |
| `exclude_defaults=True` | 等于默认值的字段 | 生成「差异配置」，少用于请求处理 |

组合使用（如 `exclude_unset=True, exclude_none=True`）会取两者交集：既要求出现过、又要求不是 None。

### 3.2 `model_fields_set`

```python
patch = ProductPatch(name="x")
patch.model_fields_set           # {'name'}
```

| 特性 | 实测结论 |
| --- | --- |
| 类型 | `set[str]` |
| 是否被 `model_dump()` 修改 | **不会**（v1 时代会重置，v2 不会） |
| 何时有用 | 审计日志、动态权限判断（「改了价格」才校验改价权限） |
| 嵌套 | 子模型的 `fields_set` 独立记录，父模型的 `fields_set` 只含子模型字段名 |

### 3.3 更新端点骨架

```python
@app.patch("/products/{product_id}")
def patch_product(product_id: int, patch: ProductPatch) -> dict[str, Any]:
    if product_id not in _PRODUCTS:
        raise HTTPException(status_code=404, detail="商品不存在")
    updates = patch.model_dump(exclude_unset=True)
    _PRODUCTS[product_id].update(updates)
    return _PRODUCTS[product_id]
```

## 4. 边界条件

### 4.1 显式 null 的两种业务语义

| 业务约定 | 期望 | 实现 |
| --- | --- | --- |
| `null` = 清空该字段 | `note` 被置 None | `exclude_unset=True` |
| `null` = 不修改 | `note` 保持原值 | `exclude_none=True`（但没有「清空」能力了） |
| 两者都要 | 用额外标记（如 `{"note": {"set": null}}`） | 自定义模型，成本高，慎用 |

**必须在接口文档里写清楚用哪种**，否则前端会踩。实测：

```text
{"note": null}  + exclude_unset → {"note": None}
{"note": null}  + exclude_none  → {}
```

### 4.2 空对象与幂等

| 请求 | 结果 | 说明 |
| --- | --- | --- |
| `{}` | 200，updates `{}` | 合法且幂等，不要返回 400 |
| `{}` 且资源不存在 | 404 | 先判存在性 |
| 重复同一 PATCH | 结果一致 | 幂等，可安全重试 |

### 4.3 嵌套字段的局部更新

```python
class Address(BaseModel):
    city: str | None = None
    street: str | None = None


class ProductPatch(BaseModel):
    address: Address | None = None
```

| 请求 | 结果 |
| --- | --- |
| `{"address": {"city": "上海"}}` | `exclude_unset` 得到 `{"address": {"city": "上海"}}`？**实测不会**——外层 `exclude_unset` 不递归 |
| 想只改 city 保留 street | 需要 `model_dump(exclude_unset=True)` 递归（v2 的 `exclude_unset` 默认不递归到子模型）|

> **不确定点（明确标注）**：`model_dump(exclude_unset=True)` 对嵌套模型是否递归排除未设置字段，本章**未做专项断言**（v2 文档提到 `exclude_unset` 对子模型的行为与 v1 不同）。工程建议：嵌套更新用「显式读取子模型字段 + 手动合并」，或拆成独立子资源接口（`PATCH /products/1/address`）。

### 4.4 并发覆盖（lost update）

两个客户端同时 PATCH 同一资源，后写的覆盖先写的。PATCH 只解决「字段粒度」，**不解决并发**。

| 方案 | 说明 |
| --- | --- |
| 版本号 `version` + `WHERE version = ?` | 推荐，冲突时 409 |
| `If-Match` + ETag | 走 HTTP 语义，补偿成本高 |
| 只允许改自己创建的资源 | 治标 |

### 4.5 404 与 422 的分工

| 情况 | 状态码 | 理由 |
| --- | --- | --- |
| 请求体字段类型/约束错 | 422 | 参数问题 |
| 资源 id 不存在 | 404 | 目标不存在 |
| 改别人的资源 | 403 | 权限 |
| 版本冲突 | 409 | 并发 |

把「不存在」写成 422 会让客户端无法区分重试策略。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 复用创建模型做 PATCH | 未传字段被写成 None | 独立 Patch 模型 | 实测 |
| 用 `model_dump()` 全量 update | 同上，等于 PUT | `exclude_unset=True` | 实测 |
| 以为 `exclude_unset` 会去掉 null | 实测保留 `{"note": None}` | 要丢就用 `exclude_none` | 实测 |
| 以为 `model_dump()` 会重置 fields_set | v2 不会，可多次读取 | 放心用 | 实测 |
| 空对象返回 400 | 客户端探活失败 | 200 + 空 updates | 实测 |
| 资源不存在返回 422 | 客户端误判 | 404 | 实测 |
| 可选字段以为不校验 | `name="笔"` 仍 422 | 可选≠免校验 | 实测 |
| 不配 `extra="forbid"` | 拼错字段静默无效 | 配上 | 实测 |
| PUT 实现局部更新 | 语义错、易清空 | 用 PATCH | `[P1]` |
| 用 `exclude_none` 还想要「清空」 | 无法表达 null | 明确语义 + `exclude_unset` | `[P2]` |
| 嵌套直接整体替换 | 子字段被清空 | 拆子资源或手动合并 | `[P2]` |
| 忽略并发 | 后写覆盖先写 | 版本号 + 409 | `[P3]` |
| 把 updates 直接 spread 到 ORM 对象 | 可能触发脏检查异常字段 | 白名单字段 | `[P4]` |
| 更新不记录审计 | 出事无法追溯 | 记录 fields_set + 操作者 | `[P5]` |
| 允许 PATCH 改 id | 主键漂移 | 模型里不含 id | `[P1]` |
| 允许 PATCH 改状态机字段 | 跳过审批流 | 状态单独接口 + 权限 | `[P4]` |
| 用 PATCH 传全量数据 | 语义混乱、日志噪声 | PUT 或 POST | `[P1]` |
| `updates` 为空仍执行 update | 触发无意义写库/审计 | 判空后跳过 | `[P5]` |
| 用 `patch.dict()` 之类第三方库 | 增加依赖且受限 | 标准 `exclude_unset` 足够 | `[P2]` |
| 单元测试只测成功路径 | 清空事故没覆盖 | 补「只传一个字段」用例 | 第 71 章 |

## 6. 最佳实践与编码建议

### 6.1 可直接抄的更新模板

```python
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()


class ProductPatch(BaseModel):
    """局部更新入参：所有字段可选，显式 null 表示清空。"""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=2, max_length=20)] = None
    price: Annotated[float | None, Field(gt=0)] = None
    note: Annotated[str | None, Field(max_length=100)] = None


@app.patch("/products/{product_id}")
def patch_product(product_id: int, patch: ProductPatch) -> dict[str, Any]:
    current = load_product(product_id)          # 不存在抛 404
    updates = patch.model_dump(exclude_unset=True)
    if not updates:                             # 空更新直接返回，避免无意义写库
        return current
    check_permission(patch.model_fields_set)    # 例如改价需要更高权限
    save_product(product_id, updates, audit=patch.model_fields_set)
    return load_product(product_id)
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| Patch 模型单独定义 | 不复用 Create/Read |
| 显式声明 null 语义 | 写进文档与测试 |
| 空更新短路 | 不写库、不记审计 |
| 用 `fields_set` 做权限 | 「改了敏感字段」才要特权 |
| 敏感字段排除 | `id`/`created_at`/`status` 不进 Patch 模型 |
| 更新后返回最新资源 | 避免客户端二次 GET |
| 并发控制用版本号 | 冲突返回 409 |

### 6.3 选型速查

| 需求 | 方法 |
| --- | --- |
| 改一个字段 | PATCH |
| 整体替换 | PUT |
| 改嵌套子对象 | PATCH 子资源 |
| 批量改多条 | 独立批量接口（第 42 章） |
| 改状态 | 专用动作接口（`/submit`、`/approve`） |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[P1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/body-updates/ | PATCH 与 `exclude_unset` 的标准写法 |
| `[P2]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/serialization/ | `exclude_unset`/`exclude_none`/`exclude_defaults` |
| `[P3]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-9.3.4 | PATCH 语义与并发 |
| `[P4]` | 规范 | https://restfulapi.net/rest-put-vs-post/ | PUT/PATCH 与资源建模 |
| `[P5]` | 工程实践 | https://fastapi.tiangolo.com/zh/tutorial/sql-databases/ | 更新后返回最新数据 |

> **核对状态**：`[P1]`–`[P5]` 为官方文档/规范链接，**本次未逐页直连复核**；`exclude_*` 行为、`fields_set`、422/404 均为本机实测，`examples/verify.py` 复现 10/10 通过。4.3 的嵌套 `exclude_unset` 是否递归**未验证**，文中已标注。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] PUT 与 PATCH 的语义差别
- [ ] `fields_set` 是什么、什么时候写入
- [ ] `exclude_unset` 与 `exclude_none` 的差别
- [ ] 显式 `null` 的两种业务语义
- [ ] 空对象为什么合法
- [ ] 404 与 422 的分工

**能写出（代码层）**：

- [ ] 全可选的 Patch 模型
- [ ] `exclude_unset` 更新端点
- [ ] `fields_set` 审计
- [ ] 空更新短路

**能判断（避坑层）**：

- [ ] 看到 PATCH 复用 Create 模型 → 指出会清空
- [ ] 看到 `model_dump()` 全量更新 → 指出等于 PUT
- [ ] 看到 `null` 被当作「不改」→ 指出与 `exclude_unset` 冲突
- [ ] 看到敏感字段进 Patch → 指出越权风险
- [ ] 看到并发覆盖 → 指出缺版本号

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] 手工发 `{"name": "x"}` 确认其他字段没变
- [ ] `/docs` 里 PATCH 无 `required`

## 9. 下一章衔接

第 19 章 `模型复用`：本章的 `ProductPatch` 与创建模型有大量重复字段。下一章讲透「基类继承 + 类型别名 + 组合」，让 Create/Patch/Read 三个模型共享字段定义而不复制约束。

本章留下的伏笔：

1. 嵌套更新是否递归排除，第 19 章讲模型拆分时会再遇到。
2. 并发控制与版本号在 M09（第 55–59 章）。
3. 审计日志在 M11（第 65–70 章）。
4. 权限判断在 M07（第 44–49 章）。
