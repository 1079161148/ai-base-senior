# 23 联合类型响应

## 一句话结论

一个端点可能返回两种结构（成功/失败、A 形态/B 形态）时，用 `response_model=A | B`，OpenAPI 会生成 `anyOf`。不同状态码对应不同模型用 `responses={404: {"model": ErrorOut}}`——它只是**文档**，真正返回由代码决定。直接 `return JSONResponse(...)` 会**完全绕过**响应模型：不校验、不过滤。

学完这一章，你能：给二选一响应建模、让文档准确反映多状态码结构、知道「绕过响应模型」的几个入口。

## 最小可运行案例

```python
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()


class ItemOut(BaseModel):
    id: int
    name: str


class SuccessOut(BaseModel):
    ok: bool = True
    data: ItemOut


class ErrorOut(BaseModel):
    ok: bool = False
    message: str


@app.get("/result/{kind}", response_model=SuccessOut | ErrorOut)
def get_result(kind: str) -> SuccessOut | ErrorOut:
    if kind == "success":
        return SuccessOut(data=ItemOut(id=1, name="键盘"))
    return ErrorOut(message="查无此项")


@app.get("/item-or-error/{item_id}", response_model=ItemOut,
         responses={404: {"model": ErrorOut, "description": "商品不存在"}})
def get_item_or_error(item_id: int) -> Any:
    if item_id == 1:
        return ItemOut(id=1, name="键盘")
    return JSONResponse(status_code=404, content={"ok": False, "message": "商品不存在"})
```

完整版本（`anyOf` 断言、`A|B` 顺序、`response_model=None`）见 `examples/main.py`。

## 怎么跑

```powershell
cd "03-响应\23-联合类型\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] OpenAPI anyOf -> anyOf=['SuccessOut', 'ErrorOut']
[PASS] 成功分支 -> ok=True，data.id=1
[PASS] 失败分支 -> message='查无此项'
[PASS] 按状态码挂模型 -> 200→ItemOut，404→ErrorOut
[PASS] 404 返回 JSONResponse -> 404 + ErrorOut 结构
[PASS] JSONResponse 绕过模型 -> 多余字段与非法类型原样输出
[PASS] A|B 匹配 A -> 匹配 A：{'ok': True, 'name': 'x'}
[PASS] B|A 匹配 B -> 匹配 B：{'ok': True, 'message': 'y'}
[PASS] 联合全不匹配 500 -> 两者都不匹配 → 500
[PASS] response_model=None -> 不过滤，原样输出

结果：10/10 通过
```

## 核心 API 速查

| 写法 | 作用 | 注意 |
| --- | --- | --- |
| `response_model=A \| B` | 二选一，OpenAPI 出 `anyOf` | 都不匹配 → 500 |
| `Union[A, B]` | 同上（Python 3.9 写法） | 顺序参与匹配 |
| `responses={404: {"model": X}}` | 为某个状态码声明文档模型 | 纯文档，不改变返回 |
| `response_model=None` | 完全不过滤 | 慎用，等于放弃保护 |
| `return JSONResponse(...)` | 绕过响应模型 | 状态码/头/体全部自己控制 |
| `response_model=list[A \| B]` | 列表里混合两种 | 元素逐个匹配（未实测） |

| 返回值类型 | 走响应模型？ | 会 500？ |
| --- | --- | --- |
| `BaseModel` 实例 | ✅ | 结构不符会 |
| `dict` | ✅ | 会 |
| `JSONResponse` / `Response` | ❌ 直接发送 | 不会 |
| `None` + `response_model` | ✅ | 会（缺失字段） |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 联合里两个模型都没有必填区分 | dict 匹配歧义 | 加判别字段（如 `ok`）|
| 以为 `responses=` 会真的转换返回 | 只是文档 | 自己 `JSONResponse` 或 `HTTPException` |
| 返回 `JSONResponse` 却声明 `response_model` | 文档骗人、字段不校验 | 用 `response_model=None` 或去掉 |
| 成功/失败用同一状态码 200 | 客户端要解析 body 才能分支 | 失败用 4xx + `responses=` |
| `A \| B` 两个模型字段完全一样 | 联合没有意义 | 用统一模型 + 判别字段 |
| 依赖联合顺序做业务判断 | 顺序改了行为就变 | 显式判别字段 |
| 联合里放 `Response` 类型 | 行为不符预期 | 用 `Any`/`response_model=None`（未实测）|
| 以为 `anyOf` 会被 SDK 当「之一」 | 部分 SDK 生成成宽松类型 | 重要接口拆成两个端点 |

## 毕业自查

- [ ] 能写出成功/失败二选一的联合响应
- [ ] 能说出 `anyOf` 与 `oneOf` 的差别（OpenAPI 层面）
- [ ] 能说出 `responses=` 是文档还是行为
- [ ] 能列出三种「绕过响应模型」的返回方式
- [ ] 能解释联合全不匹配为什么是 500
- [ ] 能判断什么时候该拆成两个端点
- [ ] 动手题一：给联合加 `discriminator`，看 OpenAPI 变化
- [ ] 动手题二：把 `/item-or-error` 改成抛 `HTTPException` 并保持 404 文档

> 想看 `anyOf`/`oneOf`/`discriminator`、联合匹配算法、SDK 生成差异、20 条坑，继续读 [`base.md`](./base.md)。
