# 23 联合类型响应 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「联合响应的匹配规则、`responses=` 的真实作用、绕过响应模型的三个入口、SDK 生成差异」拆开。学完这章，你要能判断「该用联合还是该拆端点」。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 21–22 章（响应模型、状态码） |
| 覆盖范围 | `A \| B` 响应、`anyOf`、`responses=`、`response_model=None`、`Response` 绕过 |
| 明确不覆盖 | `discriminator` 判别器深入（仅提及）、自定义响应类（第 25 章）、错误结构统一（第 33 章） |
| 学完验收 | 能跑通 `verify.py` 10/10、能预测联合匹配结果、能说出文档与行为的边界 |

## 0. 怎么用这份文件

**依据约定**：`` `[Un]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 什么场景需要联合响应
2 机制（第 2 节）    → 联合是怎么被匹配的
3 API（第 3 节）     → 联合模型 / responses / response_model=None
4 边界（第 4 节）    → 歧义、全不匹配、Response 绕过、SDK
5 注意事项（第 5 节）→ 20 条对照
6 最佳实践（第 6 节）→ 判别式设计
```

## 1. 概念：三种「一个端点多种结构」

| 形态 | 例子 | 推荐做法 |
| --- | --- | --- |
| 按状态码区分 | 200 返回对象，404 返回错误体 | 主模型 + `responses={404: ...}` |
| 按判别字段区分 | `{"ok": true, data}` / `{"ok": false, message}` | 联合 + 稳定判别字段 |
| 真的完全不同 | 返回文件流或 JSON | 拆两个端点 / 用 `Response` |

联合响应不是越多越好：客户端要为每个分支写解析，分支越多越容易漏。

## 2. 机制：联合是怎么被匹配的

```text
返回值 → 若为 BaseModel 实例：逐分支 isinstance 匹配（实测按声明顺序）
       → 若为 dict：逐分支做校验，第一个通过者胜出
       → 全不通过：ResponseValidationError → 500
```

实测：

| 响应模型 | 返回 | 结果 |
| --- | --- | --- |
| `A \| B`（A=ok+name，B=ok+message） | `{"ok": true, "name": "x"}` | 匹配 A |
| `B \| A` | `{"ok": true, "message": "y"}` | 匹配 B |
| `A \| B` | `{"ok": true}` | 都不匹配 → 500 |

关键：**dict 匹配靠「谁先通过校验」**，所以两个分支不能有完全重叠的字段集合，否则结果取决于顺序。

## 3. API 逐个拆解

### 3.1 `response_model=A | B`

| 要点 | 说明 |
| --- | --- |
| OpenAPI | `anyOf: [A, B]`（实测顺序与声明一致） |
| `required` | 每个分支各自的 required |
| 校验 | 一次只走一个分支 |
| 错误 | 都不匹配 → 500，日志里两个分支的错误都在 |

### 3.2 `responses={...}`

```python
@app.get("/item-or-error/{item_id}", response_model=ItemOut,
         responses={404: {"model": ErrorOut, "description": "商品不存在"}})
```

| 事实 | 说明 |
| --- | --- |
| 只影响 OpenAPI | 不会改变返回值、不会加校验 |
| 支持 `model` / `description` / `content` | `model` 会被转成 `$ref` |
| 可以和 `response_model` 并存 | 200 用主模型，其它用 responses |
| 常见用途 | 让 SDK 知道 404/409/429 的 body 结构 |

实测：`responses` 里 404 的 `$ref` 是 `ErrorOut`，200 是 `ItemOut`，两个组件都在 `components.schemas`。

### 3.3 绕过响应模型的三种返回

| 返回 | 是否走响应模型 | 后果 |
| --- | --- | --- |
| `JSONResponse(...)` | ❌ | 不校验、不过滤、状态码自定 |
| `Response(...)` / `PlainTextResponse` | ❌ | 同上，媒体类型自定 |
| `StreamingResponse` | ❌ | 同上，适合大文件 |

实测：`/raw` 返回 `JSONResponse` 里带 `secret` 与非法类型 `count="不是数字"`，客户端原样收到——**没有任何校验**。

### 3.4 `response_model=None`

| 用途 | 风险 |
| --- | --- |
| 临时关闭过滤 | 字段泄露、无文档 |
| 返回结构动态 | SDK 无法生成 |

只在「结构确实无法静态描述」时用，并在注释里写清原因。

## 4. 边界条件

### 4.1 联合歧义

| 场景 | 结果 |
| --- | --- |
| A、B 字段集合相同、只有语义不同 | 永远匹配第一个 → 不可控 |
| A 的字段是 B 的子集 | 取决于顺序，风险高 |
| 有稳定判别字段（`ok`/`type`） | 可预测 |

建议：联合成员必须有**互斥的必填字段**或**字面量判别字段**：

```python
class SuccessOut(BaseModel):
    ok: Literal[True] = True


class ErrorOut(BaseModel):
    ok: Literal[False] = False
```

（`Literal` 判别在本章示例里用 `bool` 简化，严格版要用 `Literal`。）

### 4.2 状态码与 body 的一致性

| 情况 | 评价 |
| --- | --- |
| 200 返回错误结构 | ❌ 客户端/网关无法统一处理 |
| 404 返回错误结构 + `responses=` 声明 | ✅ |
| 404 返回主模型结构 | ❌ 文档骗人 |

### 4.3 `JSONResponse` 与 `HTTPException` 的区别

| 方式 | body 结构 | 是否走异常处理器 |
| --- | --- | --- |
| `raise HTTPException(404, detail=...)` | 固定 `{"detail": ...}` | ✅ 可统一改（第 33 章）|
| `return JSONResponse(404, {"ok": false, ...})` | 完全自定义 | ❌ |

团队要么统一用 `HTTPException` + 异常处理器，要么统一用 `JSONResponse`；混用会导致错误结构不一致。

### 4.4 SDK 生成

| 结构 | SDK 表现 |
| --- | --- |
| `anyOf` | 生成宽松类型 / 联合类型（各语言不同）|
| 两个端点 | 类型精确 |
| `response_model=None` | 生成 `Any` / `object` |

对外 API 若给第三方用，**重要接口建议拆端点**，别让 SDK 猜。

### 4.5 性能

联合校验成本 ≈ 各分支校验之和（最坏情况全部走一遍）。高 QPS 接口避免 3 个以上分支。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 联合成员字段集合完全相同 | 永远匹配第一个 | 加判别字段 | 实测 |
| 靠顺序做业务语义 | 改顺序就改行为 | 显式判别 | 实测 |
| 以为 `responses=` 会真的转换返回 | 只是文档 | 自己控制返回 | 实测 |
| `JSONResponse` + `response_model` 并存 | 文档与实际不符 | 去掉 `response_model` | 实测 |
| 失败也用 200 | 客户端要读 body 分支 | 4xx | `[U1]` |
| 联合里塞 4 个分支 | 校验成本、客户端复杂 | 拆端点 | `[U3]` |
| 用 `response_model=None` 图省事 | 泄露、无文档 | 显式模型 | 实测 |
| 让 `anyOf` 支撑重要第三方契约 | SDK 体验差 | 拆端点 | `[U2]` |
| 混用 `HTTPException` 与 `JSONResponse` | 错误结构不一致 | 统一一种 | 第 33 章 |
| 联合分支里放 `Response` 类型 | 行为不确定 | 单独端点 | `[U2]` |
| 忘记 `responses` 里写 description | 文档空白 | 补上 | `[U1]` |
| 以为 500 会被客户端友好处理 | 客户端只看到通用错误 | 用 4xx 表达业务失败 | `[U1]` |
| 联合模型里字段可选太多 | 匹配变宽松、歧义增加 | 收紧必填 | 实测 |
| 用联合表达「分页」 | 结构本可统一 | 统一 envelope | `[U3]` |
| 用联合表达「文件或 JSON」 | 客户端无法预判 | `Content-Type` 协商 | 第 25 章 |
| 忽略 `Content-Type` | SDK 解析失败 | 正确媒体类型 | `[U1]` |
| 断言 OpenAPI 用 `str(schema)` | docstring 干扰 | 断言具体字段 | 第 21 章 |
| 只测一个分支 | 另一分支 500 无人知 | 每分支一条用例 | 第 71 章 |
| 用 `Union[None, A]` 表示「可能空」 | 客户端要判空 | 明确 204/404 | 第 22 章 |
| 依赖 `anyOf` 顺序生成 mock | 顺序可能变 | 不依赖 | `[U2]` |
| `anyOf` 里混入 `list[X]` 分支 | 部分生成器类型不稳 | 拆端点 | `[U2]` |

## 6. 最佳实践与编码建议

### 6.1 判别式联合模板

```python
from typing import Literal

from pydantic import BaseModel


class SuccessOut(BaseModel):
    ok: Literal[True] = True
    data: ItemOut


class ErrorOut(BaseModel):
    ok: Literal[False] = False
    message: str


@app.get("/result/{kind}", response_model=SuccessOut | ErrorOut)
def get_result(kind: str) -> SuccessOut | ErrorOut:
    ...
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 判别字段用 `Literal` | 匹配稳定、文档清晰 |
| 失败配 4xx + `responses=` | 文档与行为一致 |
| 分支数 ≤2 | 多了就拆 |
| 对外接口优先拆端点 | SDK 友好 |
| 错误结构统一 | 别混用两种返回方式 |
| `response_model=None` 必须写理由 | 注释说明 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 成功/失败 | 联合 + `ok` 判别 |
| 按状态码 | 主模型 + `responses=` |
| 文件或 JSON | 拆端点或 `Content-Type` 协商 |
| 结构动态 | `response_model=None` + 文档手写 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[U1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/additional-responses/ | `responses=` 用法 |
| `[U2]` | 规范 | https://spec.openapis.org/oas/latest.html#schema-object | `anyOf`/`oneOf`/`discriminator` |
| `[U3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/response-model/ | 响应模型整体约束 |
| `[U4]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/custom-response/ | 直接返回 Response |

> **核对状态**：`[U1]`–`[U4]` 为官方文档/规范链接，**本次未逐页直连复核**；`anyOf` 生成、按状态码挂模型、`JSONResponse` 绕过、联合全不匹配 500 均为本机实测，`examples/verify.py` 复现 10/10 通过。`discriminator` 与 `list[A|B]` **未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三种「一个端点多种结构」的取舍
- [ ] 联合的匹配规则
- [ ] `responses=` 是文档不是行为
- [ ] 三种绕过响应模型的返回
- [ ] 联合全不匹配为什么 500

**能写出（代码层）**：

- [ ] `A | B` 响应
- [ ] `responses={404: {"model": X}}`
- [ ] `JSONResponse` 自定义错误体
- [ ] `Literal` 判别字段

**能判断（避坑层）**：

- [ ] 看到联合成员字段重合 → 指出歧义
- [ ] 看到 `JSONResponse` + `response_model` → 指出文档骗人
- [ ] 看到失败 200 → 指出客户端分支成本
- [ ] 看到 4 个分支 → 指出该拆
- [ ] 看到 `response_model=None` → 追问理由

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] `/docs` 里看到 `anyOf` 与两个组件
- [ ] 手工验证 404 分支结构

## 9. 下一章衔接

第 24 章 `响应头`：本章的 `Location` 只是提了一句。下一章系统讲 `Response` 注入改头、`headers` 参数、`Set-Cookie` 与 `Content-Type`、以及为什么「响应头不能用模型声明」。

本章留下的伏笔：

1. `Content-Type` 协商在 第 25 章。
2. 错误响应统一结构在 第 33 章。
3. 自定义 OpenAPI 在 第 26 章。
4. 分页 envelope 设计在 M11。
