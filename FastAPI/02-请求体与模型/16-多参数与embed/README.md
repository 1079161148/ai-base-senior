# 16 多参数与 embed

## 一句话结论

路径/查询/头与 body 可以同时出现在一个接口里，互不干扰。**单个** body 参数收裸对象；**多个** body 参数会被 FastAPI 自动包装成 `{"参数名": 值}`（键名就是函数参数名）；`Body(embed=True)` 让单个 body 参数也强制包装。

学完这一章，你能：正确混用四类位置 + body、判断什么时候必须包装、用 `embed` 提前锁定契约形状。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import Body, FastAPI, Path, Query
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    sku: str
    qty: int


# 单 body：请求体就是 {"sku": "A-1", "qty": 2}
@app.post("/orders/{order_id}/items")
def add_item(
    order_id: Annotated[int, Path(ge=1)],
    item: Item,
    notify: Annotated[bool, Query()] = False,
) -> dict[str, object]:
    return {"order_id": order_id, "item": item.model_dump(), "notify": notify}


# 单 body + embed：请求体必须是 {"coupon": {...}}
@app.post("/coupons")
def create_coupon(coupon: Annotated[Item, Body(embed=True)]) -> dict[str, object]:
    return {"coupon": coupon.model_dump()}
```

完整版本（两个 body 参数、标量 body、OpenAPI 组件）见 `examples/main.py`。

## 怎么跑

```powershell
cd "02-请求体与模型\16-多参数与embed\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 混合参数正常 -> order_id=9 notify=True item=裸对象
[PASS] 混合参数 body 错误 loc -> loc=['body', 'qty']
[PASS] 多 body 包装 -> 包装后 200
[PASS] 多 body 未包装 -> loc 集合=[('body', 'address'), ('body', 'item')]
[PASS] 多 body 缺一个 -> loc=["body","address"]
[PASS] embed 裸对象被拒 -> 422 missing loc=['body', 'coupon']
[PASS] embed 包装通过 -> 包装后 200
[PASS] 标量 body 包装 -> 包装后 200；未包装 422
[PASS] 包装键名 = 参数名 -> 键名必须是 "item"（参数名）
[PASS] OpenAPI Body_* 组件 -> Body_* 组件 3 个；单 body 直连模型
[PASS] GET 不带 body 契约 -> 订单条目只能 POST；GET 带 body 不建议

结果：11/11 通过
```

## 核心 API 速查

| 声明 | 请求体形状 | 状态 |
| --- | --- | --- |
| `item: Item`（唯一 body） | `{"sku":...}` | 裸对象 |
| `item: Item, user: User`（两个 body） | `{"item":{...},"user":{...}}` | 自动包装 |
| `Annotated[Item, Body(embed=True)]` | `{"item":{...}}` | 强制包装 |
| `Annotated[str, Body()]` + `item: Item` | `{"token":"x","item":{...}}` | 标量也算 body，一起包装 |
| `order_id: Annotated[int, Path()]` + `item: Item` | 路径 + 裸对象 | 互不影响 |
| `notify: Annotated[bool, Query()] = False` + `item: Item` | 查询 + 裸对象 | 互不影响 |

| 位置 | 打包进 body 吗 | 错误 `loc` 首段 |
| --- | --- | --- |
| 路径 | ❌ | `path` |
| 查询 | ❌ | `query` |
| 请求头 | ❌ | `header` |
| Cookie | ❌ | `cookie` |
| 单个 body 参数 | 裸对象 | `body` |
| 多个 body 参数 | 按参数名包装 | `body` + 参数名 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 两个 body 参数却发扁平 JSON | 422 两条 `missing`，`loc=["body","item"]` | 按参数名包装 |
| 以为包装键可自定义 | 键名 = 函数参数名，改名即破坏契约 | 用 `alias` 或固定命名 |
| 单 body 加了 `embed=True` 却发裸对象 | 422 `loc=["body","coupon"]` | 包装一层 |
| 以后可能加第二个 body 却不用 embed | 上线后形状变更 = 破坏性变更 | 先 `embed=True` |
| 在 JSON 顶层传两个对象（非法 JSON） | 解析失败 | 用包装对象 |
| 把查询参数塞进 body | 分页/过滤语义错位 | 分页放 query |
| 多 body 里混标量 | 忘了标量也要包装 | 一起包 |
| 用 GET 传 body | 技术上能跑，但网关/缓存不保证 | 用 POST |

## 毕业自查

- [ ] 能说出「单 body」与「多 body」的请求体形状差异
- [ ] 能说出包装键名由什么决定
- [ ] 能说出 `embed=True` 解决什么问题
- [ ] 能写出「路径 + 查询 + 头 + body」四件套接口
- [ ] 能读懂混合参数下 422 里各条错误的 `loc` 首段
- [ ] 能说出 OpenAPI 里 `Body_*` 组件从哪来
- [ ] 动手题一：给 `/coupons` 加一个 `count: Annotated[int, Body(gt=0)]`，观察包装变化
- [ ] 动手题二：把 `/shipments` 的参数名 `item` 改成 `goods`，验证旧报文报错

> 想看打包规则细节、`Body_*` 组件命名、`embed` 的版本兼容取舍、21 条坑，继续读 [`base.md`](./base.md)。
