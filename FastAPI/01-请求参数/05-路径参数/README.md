# 05 路径参数

## 一句话结论

路径参数是 URL **路径段**里的变量，声明为函数参数即可自动注入。写了类型标注就会做**类型转换**：转换失败返回 422；而用 `{id:int}` 这种**转换器**则在正则层就不匹配，返回 404。

学完这一章，你能：正确声明路径参数、区分 404 与 422 的边界、说清 `bool` 参数的坑。

## 最小可运行案例

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/users/{user_id}")
def get_user(user_id: int) -> dict[str, object]:
    # 【作用】user_id 会自动从 "/users/42" 里取出并转成 int
    return {"user_id": user_id, "type": type(user_id).__name__}


@app.get("/products/{code:int}")
def get_product(code: int) -> dict[str, int]:
    # 【作用】{code:int} 是正则层约束：/products/abc 直接 404，不会进函数
    return {"code": code}
```

完整版本见 `examples/main.py`。

## 怎么跑

```powershell
cd "01-请求参数\05-路径参数\examples"
uv run uvicorn main:app --reload

# 或直接验收
uv run python verify.py
```

预期输出：

```text
[PASS] int 转换 -> 200 {'user_id': 42, 'type': 'int'}
[PASS] 负数也是 int -> -7
[PASS] float 转换 -> 3.14
[PASS] bool 接受 true/1/yes -> [True, True, True]
[PASS] 非法 int 返回 422 -> int_parsing
[PASS] 转换器不匹配返回 404 -> /products/abc
[PASS] 多路径参数 -> {'from_city': '北京', 'to_city': '上海'}
[PASS] 路径参数必填（不写会启动报错） -> 已确认

结果：8/8 通过
```

## 核心 API 速查

| 写法 | 位置 | 说明 |
| --- | --- | --- |
| `@app.get("/users/{user_id}")` | 装饰器 | 声明路径模板 |
| `def get_user(user_id: int)` | 函数 | 同名参数自动注入 |
| `{v:path}` | 路径 | 匹配含斜杠的剩余部分 |
| `{v:int}` / `{v:float}` / `{v:uuid}` | 路径 | 正则层约束 |

| 标注类型 | 输入 → 输出 | 失败状态码 | 失败 `type` |
| --- | --- | --- | --- |
| `int` | `"42"` → `42` | 422 | `int_parsing` |
| `float` | `"3.14"` → `3.14` | 422 | `float_parsing` |
| `str` | `"abc"` → `"abc"` | — | — |
| `bool` | `"true"/"1"/"yes"` → `True` | 422 | `bool_parsing` |
| `UUID` | `"..."` → `UUID` | 422 | `uuid_parsing` |
| `datetime` | ISO 8601 → `datetime` | 422 | `datetime_parsing` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为 `bool` 只认 `true/false` | 实测 `1`、`yes` 也转成 `True`，`0` → `False` | 布尔路径参数几乎没用，改用 `str` + 显式映射 |
| 以为 `/products/abc` 会 422 | 用 `{code:int}` 时是 **404**（正则不匹配） | 要 422 就用标注 `int`，要 404 就用 `{code:int}` |
| 路径参数给默认值 | 实测**不报错**，但默认值完全无效、参数仍必填（OpenAPI 里仍 `required: true` 且无 `default`） | 干脆不写默认值；要可选就改成查询参数 |
| 路径参数名与函数参数名不一致 | 报 `Field required` 或缺值 | 名字必须一致，或用 `Path(alias=...)` |
| 用路径参数传敏感信息 | 会进日志、浏览器历史、Referer | 用 Header 或 Body |
| 路径段里放空格或中文 | 需要 URL 编码，前端易出错 | 用 ID + 查询参数 |
| 用 `str` 接收 ID 后再手工 `int()` | 重复校验、错误码不统一 | 直接标注 `int` |

## 毕业自查

- [ ] 能说出路径参数与查询参数的三个区别
- [ ] 能说出 `{v:int}` 与 `v: int` 的失败状态码差异
- [ ] 能列举 `bool` 路径参数接受的 6 种写法
- [ ] 能说出路径参数写默认值会发生什么（实测：静默失效）
- [ ] 能解释 422 响应里 `loc` 字段的含义
- [ ] 动手题一：加一个 `/users/{user_id}/orders/{order_id}` 双参数接口
- [ ] 动手题二：把 `/products/{code:int}` 改成 `{code}`，观察 404 变 422

> 想看类型转换表、422 结构、转换器原理、32 条坑，继续读 [`base.md`](./base.md)。
