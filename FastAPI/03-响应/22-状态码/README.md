# 22 状态码

## 一句话结论

默认 200 只是「没写」。创建写 `201`、删除写 `204`、异步受理 `202`、冲突 `409`。三种改法：装饰器 `status_code=`、注入 `Response` 改 `status_code`、抛 `HTTPException`。**204 不能有 body**——FastAPI 在注册路由时就用 `AssertionError` 卡住你（实测）。

学完这一章，你能：给每个端点选对状态码、知道三者谁覆盖谁、知道 204/1xx 的 body 限制、知道 201 不会自动加 `Location`。

## 最小可运行案例

```python
from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel

app = FastAPI()


class ItemIn(BaseModel):
    name: str


class ItemOut(BaseModel):
    id: int
    name: str


_ITEMS: dict[int, ItemOut] = {}


@app.post("/items", status_code=status.HTTP_201_CREATED, response_model=ItemOut)
def create_item(item: ItemIn) -> ItemOut:
    created = ItemOut(id=1, name=item.name)
    _ITEMS[1] = created
    return created              # 状态码 201


@app.post("/items/async", status_code=201, response_model=ItemOut)
def create_async(item: ItemIn, response: Response) -> ItemOut:
    response.status_code = status.HTTP_202_ACCEPTED   # 函数内覆盖装饰器
    return ItemOut(id=0, name=item.name)


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int) -> None:                # 204 只能返回 None
    if item_id not in _ITEMS:
        raise HTTPException(status_code=404, detail="商品不存在")   # 404 覆盖一切
    _ITEMS.pop(item_id)
```

完整版本（OpenAPI 断言、自定义码、非法码报错）见 `examples/main.py`。

## 怎么跑

```powershell
cd "03-响应\22-状态码\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 装饰器改码 -> 201 Created，id=1
[PASS] status 常量 -> 201/202/204 常量值正确
[PASS] OpenAPI 201 -> responses=['201', '422']
[PASS] Response 注入改码 -> 装饰器 201 被函数内 202 覆盖
[PASS] 204 无 body -> 204，body 长度 0
[PASS] OpenAPI 204 无 content -> 204 响应无 content 字段
[PASS] 204 带 body 定义期报错 -> AssertionError: Status code 204 must not have a response body
[PASS] HTTPException 覆盖 -> 404 覆盖默认 200
[PASS] 自定义状态码 -> 299 正常返回
[PASS] 非法状态码报错 -> AssertionError: Status code 99 must not have a response body
[PASS] 201 无 Location -> 默认无 Location 头（需要自己加）

结果：11/11 通过
```

## 核心 API 速查

| 改码方式 | 写法 | 优先级 | 适用 |
| --- | --- | --- | --- |
| 装饰器 | `@app.post(..., status_code=201)` | 低 | 固定语义 |
| 注入 `Response` | `response.status_code = 202` | 中，覆盖装饰器 | 运行时判断 |
| 抛异常 | `raise HTTPException(404)` | 高，覆盖前两者 | 错误分支 |

| 场景 | 码 | 备注 |
| --- | --- | --- |
| 创建成功 | 201 | 可加 `Location` 头（需自己加）|
| 异步受理 | 202 | 返回任务 id |
| 删除/无内容 | 204 | **不能有 body** |
| 未修改（条件请求）| 304 | 也不能有 body |
| 参数校验失败 | 422 | FastAPI 默认 |
| 未认证/无权限 | 401 / 403 | 第 44 章 |
| 冲突 | 409 | 唯一键、版本冲突 |
| 限流 | 429 | 第 51 章 |
| 服务端错误 | 500 | 不要在业务里主动抛 500 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 204 端点写 `-> dict` | **导入期** `AssertionError: Status code 204 must not have a response body` | 返回注解写 `None` |
| 以为 204 + body 会被静默丢弃 | 根本启动不了 | 同上 |
| 1xx 状态码 | 同样报「must not have a response body」 | 别用 1xx 做业务码 |
| 创建返回 200 | 客户端无法区分成功与查询 | 用 201 |
| 以为 201 会自动加 `Location` | 实测没有 | 自己注入 `Response` 加 `headers` |
| 装饰器与函数内都改码 | 以函数内为准，装饰器文档与实际不一致 | 只改一处 |
| 用 200 表达「创建失败」 | 客户端无法统一处理 | 4xx + 明确 detail |
| 业务错误抛 500 | 监控误判为服务故障 | 用 4xx |

## 毕业自查

- [ ] 能说出三种改码方式的覆盖顺序
- [ ] 能说出 204 为什么不能有 body
- [ ] 能说出 201 与 `Location` 头的关系
- [ ] 能列出 5 个常用状态码的业务含义
- [ ] 能解释为什么「创建成功」不该返回 200
- [ ] 能解释 422 与 400 的选择
- [ ] 动手题一：给创建接口加 `Location: /items/{id}` 头
- [ ] 动手题二：让「已存在」的创建返回 409，并写一条断言

> 想看状态码与 OpenAPI 的对应、1xx/204/304 的 body 规则、错误码设计、20 条坑，继续读 [`base.md`](./base.md)。
