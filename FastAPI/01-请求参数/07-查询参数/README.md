# 07 查询参数

## 一句话结论

函数参数**没有**出现在路径模板里，它就是查询参数。**有默认值 = 可选，没默认值 = 必填**（缺失返回 422 `missing`）。`list[str]` 用重复键接收多值，**不会**自动按逗号拆分。

学完这一章，你能：正确设计列表/分页/过滤接口的查询参数、说清「`?tag=a,b` 为什么只得到一个元素」。

## 最小可运行案例

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/search")
def search(
    q: str | None = None,      # 可选：不传就是 None
    limit: int = 10,           # 可选：不传就是 10
) -> dict[str, object]:
    # 【注意】q 没出现在路径模板里 → 它是查询参数
    # 【注意】`str | None = None` 让 OpenAPI 生成 anyOf[string, null]
    return {"q": q, "limit": limit}


@app.get("/reports")
def reports(month: str) -> dict[str, str]:
    # 【注意】没有默认值 → 必填；不传返回 422 missing
    return {"month": month}
```

完整版本（多值、bool、中文）见 `examples/main.py`。

## 怎么跑

```powershell
cd "01-请求参数\07-查询参数\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 可选参数取默认值 -> {'q': None, 'limit': 10}
[PASS] 传参覆盖默认值 -> {'q': 'x', 'limit': 5}
[PASS] 必填缺失 422 missing -> 422 missing loc=['query', 'month']
[PASS] 空字符串算已传 -> ?month= → 200 而非 422
[PASS] list 用重复键 -> {'tag': ['a', 'b'], 'count': 2}
[PASS] 逗号不自动拆分 -> 内置 ['a,b']；自解析 ['a', 'b', 'c']
[PASS] bool 六种写法 -> true/1/yes→True, 0/false→False, maybe/裸键→422
[PASS] 中文与空格编码 -> 北京 / hello world 均正确解码
[PASS] OpenAPI required/default -> q:false/None, limit:false/10, month:true, tag:array

结果：9/9 通过
```

## 核心 API 速查

| 声明 | 可选性 | 缺省时 | OpenAPI |
| --- | --- | --- | --- |
| `q: str` | 必填 | 422 `missing` | `required: true` |
| `q: str = "x"` | 可选 | `"x"` | `required: false, default: "x"` |
| `q: str \| None = None` | 可选 | `None` | `anyOf[string, null]` |
| `q: str = ""` | 可选 | `""` | `default: ""` |
| `tag: list[str] = []` | 可选 | `[]` | `type: array` |
| `flag: bool = False` | 可选 | `False` | `type: boolean` |

| 多值写法 | 请求 | 收到 |
| --- | --- | --- |
| 重复键 | `?tag=a&tag=b` | `["a", "b"]` |
| 逗号拼接 | `?tag=a,b` | `["a,b"]`（**一个元素**） |
| 空值 | `?tag=` | `[""]` |

| bool 输入 | 结果 |
| --- | --- |
| `true` / `1` / `yes` / `on` | `True` |
| `false` / `0` / `no` / `off` | `False` |
| `maybe` | 422 `bool_parsing` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为 `?tag=a,b` 会拆成两个 | 实测得到 `["a,b"]` 一个元素 | 用重复键 `?tag=a&tag=b`，或后端自己 `split(",")` |
| 想用 `str = None` 表示可选 | 类型不匹配（3.10+ 会报） | `str \| None = None` |
| 必填参数没默认值却期望可选 | 422 `missing` | 给默认值 |
| `int = None` 表示可选 | 类型不符 | `int \| None = None` |
| 用查询参数传大段 JSON | URL 长度限制、日志膨胀 | 用 POST + body |
| 分页参数不设上限 | `?limit=1000000` 拖垮数据库 | `Query(le=100)`（第 08 章） |
| 用 `bool` 却传 `?flag`（无值） | 422 | 显式 `?flag=true` 或给默认值 |
| 参数名带下划线给前端 | 前端常写成 `page-size` | 用 `Query(alias="page-size")` |
| 忘记 URL 编码中文 | 请求行非法 | 客户端 `encodeURIComponent` |

## 毕业自查

- [ ] 能说出查询参数与路径参数的三个区别
- [ ] 能说出「有默认值 = 可选」的完整规则
- [ ] 能说出 `list[str]` 用哪种写法传多值
- [ ] 能说出 `?tag=a,b` 的实际结果
- [ ] 能列出 bool 的 6 种写法
- [ ] 能读懂 422 `missing` 的 `loc`
- [ ] 动手题一：加一个 `tags: list[str]` 参数，用两种写法各传一次
- [ ] 动手题二：把 `limit` 改成 `int | None = None`，观察 OpenAPI 变化

> 想看可选性规则、OpenAPI 映射、多值原理、31 条坑，继续读 [`base.md`](./base.md)。
