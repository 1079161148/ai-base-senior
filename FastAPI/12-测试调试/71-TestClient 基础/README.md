# 71 TestClient 基础

## 一句话结论

`TestClient(app)` 直接走 ASGI 协议，不开端口、不走网络，所以测试快且稳定。测试必须覆盖**三层**：成功（实测 `201` + 精确 body）、资源不存在（`404` + `detail` 文案）、参数非法（`422` + `detail[0].type` 与 `loc`）。实测要点：默认 `follow_redirects=True`（307 直接跟到 200）；不用 `with` 时 lifespan **不执行**（`started=False`）；默认 `raise_server_exceptions=True` 会把服务端异常原样抛出，避免「500 也算通过」的假绿。

## 最小可运行案例

```python
# main.py
from fastapi import FastAPI, HTTPException

app = FastAPI()
ITEMS = {1: {"id": 1, "name": "键盘"}}


@app.get("/items/{item_id}")
def read_item(item_id: int) -> dict:
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item
```

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def test_read_item(client):
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json()["name"] == "键盘"


def test_item_not_found(client):
    response = client.get("/items/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "item not found"


@pytest.mark.parametrize("limit", [0, 51, "abc"])
def test_invalid_limit(client, limit):
    assert client.get("/items", params={"limit": limit}).status_code == 422
```

## 怎么跑

```powershell
cd "12-测试调试\71-TestClient 基础\examples"
uv sync
uv run python verify.py
uv run pytest -q
```

预期输出：

```text
[PASS] 创建 201 -> 201 / id=2
[PASS] 列表 200 -> 200 / 1 条
[PASS] 详情 200 -> 键盘
[PASS] 404 detail -> 404 / item not found
[PASS] 422 body -> string_too_short + greater_than_equal
[PASS] 422 query 范围 -> limit=0 → 422
[PASS] 422 query 类型 -> limit=abc → int_parsing
[PASS] content-type -> application/json
[PASS] 跟随重定向 -> 307 → 200
[PASS] 不跟随重定向 -> 307 / location=/items
[PASS] cookie 保持 -> session=abc123
[PASS] 无 with 不跑 lifespan -> started=False
[PASS] with 跑 lifespan -> started=True
[PASS] 严格模式抛异常 -> 故意炸了
[PASS] 宽松模式 500 -> 500 Internal Server Error
[PASS] request 反查 -> GET http://testserver/items/1

结果：16/16 通过
```

`pytest -q` 另外输出 14 个用例全绿。

## 核心 API 速查

| 用法 | 说明 |
| --- | --- |
| `TestClient(app)` | 走 ASGI 直连 |
| `with TestClient(app) as c` | 进入跑 lifespan，退出跑 shutdown |
| `c.get(url, params={...})` | query 参数 |
| `c.post(url, json={...})` | JSON body |
| `c.post(url, data={...})` | 表单 |
| `c.post(url, files={...})` | 文件 |
| `c.cookies.set(k, v)` | 设 cookie |
| `follow_redirects=False` | 不跟随 3xx |
| `raise_server_exceptions=False` | 500 可断言 |
| `response.request` | 反查方法与 URL |

| 实测 | 值 |
| --- | --- |
| `POST /items` 合法 | 201 + `{"id":2,...}` |
| `GET /items/999` | 404 + `item not found` |
| body 非法 | `string_too_short` + `greater_than_equal` |
| `limit=0` | 422，`loc=["query","limit"]` |
| `limit=abc` | 422 `int_parsing` |
| `GET /redirect` 默认 | 200，`url.path=/items` |
| `follow_redirects=False` | 307 + `location: /items` |
| 不用 `with` | `started=False` |
| 用 `with` | `started=True` |
| `/boom` 默认 | 抛 `RuntimeError` |
| `/boom` 宽松 | 500 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 只测 200 | 错误路径裸奔 | 加 404/422 |
| 断言 `msg` 全文 | pydantic 升级就红 | 断言 `type` + `loc` |
| 断言整个 422 body | 多一个字段就红 | 只取需要的键 |
| 不用 `with` | lifespan 没跑，资源是 None | `with TestClient` |
| 测试间共享数据 | 顺序依赖 | fixture 里重置 |
| `raise_server_exceptions` 忘了 | 500 也算通过 | 保持默认严格 |
| 用 `client.get("/x?y=1")` 拼串 | 特殊字符没转义 | 用 `params=` |
| 对真实网络测试 | 慢且不稳 | `TestClient` |
| 断言时间戳/随机 ID | 不稳定 | 断言形状与类型 |
| 一个用例测十个接口 | 失败难定位 | 一接口一用例 |
| 忘记 `import main` 的路径 | `ModuleNotFoundError` | 配 `pythonpath` |
| 测试里改全局状态不还原 | 污染后续 | fixture `yield` 后清理 |
| 用 `pytest.ini` 与 `pyproject` 双配置 | 配置打架 | 只留一处 |
| 断言 `content-type` 带 charset | 版本差异 | 用 `startswith` 或精确值确认 |
| `client.cookies` 跨 client 共享 | 串号 | 每个 client 独立 |
| 断言日志输出 | 脆弱 | 用 caplog |
| 依赖真实数据库 | 慢 | 覆盖依赖（73 章）|
| 测试数量少就自信 | 覆盖不全 | 按三层矩阵补 |

## 毕业自查

- [ ] 能写 fixture + `with TestClient`
- [ ] 能覆盖 200/404/422 三层
- [ ] 能断言 422 的 `type` 与 `loc`
- [ ] 能用 `params` / `json` / `files`
- [ ] 知道 `raise_server_exceptions` 的作用
- [ ] 动手题一：给 `/items` 补 `limit` 边界参数化
- [ ] 动手题二：给 `create_item` 补「同名 409」

> 想看 `TestClient` 与 httpx 的关系、portal 线程、`ASGITransport`、测试目录组织、18 条坑，继续读 [`base.md`](./base.md)。