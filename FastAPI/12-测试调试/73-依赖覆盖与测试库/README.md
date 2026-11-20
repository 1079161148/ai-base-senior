# 73 依赖覆盖与测试库

## 一句话结论

`app.dependency_overrides[get_db] = fake_db` 让「**真实路由 + 假数据库**」成为可能：schema、参数校验、响应序列化全是真的，只有数据层被换掉。实测要点：key 必须是**函数对象本身**（`main.get_db`），不是字符串；嵌套依赖会自动跟随（只覆盖 `get_db`，`get_repo` 不用动）；假库写入**不污染**真实库（假库 id=10，真实库仍是 `[1,2]`）；覆盖**不改** `openapi()`（4 条路径不变）；覆盖是全局的，`finally` 里必须 `clear()`。

## 最小可运行案例

```python
# main.py
from typing import Annotated, Iterator

from fastapi import Depends, FastAPI, HTTPException

app = FastAPI()
REAL_DB = {"users": {1: {"id": 1, "name": "真实用户"}}, "next_id": 2}


def get_db() -> Iterator[dict]:
    yield REAL_DB


DBDep = Annotated[dict, Depends(get_db)]


@app.get("/users")
def list_users(db: DBDep) -> list[dict]:
    return list(db["users"].values())


@app.get("/users/{user_id}")
def read_user(user_id: int, db: DBDep) -> dict:
    user = db["users"].get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user
```

```python
# tests/test_overrides.py
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    fake = {"users": {9: {"id": 9, "name": "假用户"}}, "next_id": 10}
    main.app.dependency_overrides[main.get_db] = lambda: fake
    try:
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        main.app.dependency_overrides.clear()


def test_fake_db(client):
    assert client.get("/users").json() == [{"id": 9, "name": "假用户"}]


def test_real_id_missing(client):
    assert client.get("/users/1").status_code == 404
```

## 怎么跑

```powershell
cd "12-测试调试\73-依赖覆盖与测试库\examples"
uv sync
uv run python verify.py
uv run pytest -q
```

预期输出：

```text
[PASS] 真实数据 -> 2 条真实用户
[PASS] 假库数据 -> 1 条假用户
[PASS] 假库详情 -> 9 → 200 / 1 → 404
[PASS] 真实库不污染 -> 假库 id=10，真实库仍 [1,2]
[PASS] 原始鉴权 -> 401 → 带令牌 200
[PASS] 绕过鉴权 -> user=tester
[PASS] 覆盖配置 -> max_items=1，列表被截断到 1
[PASS] 嵌套依赖跟随 -> get_repo 未覆盖，仍用假库
[PASS] schema 不变 -> 4 条路径不变
[PASS] 清理后恢复 -> 恢复 2 条 + 401
[PASS] key 是函数对象 -> get_db / get_settings
[PASS] lambda 替身 -> lambda 可用
[PASS] 422 仍生效 -> 422 string_too_short
[PASS] 404 仍生效 -> 不存在路由仍 404
[PASS] 异常也清理 -> 异常后仍清理干净

结果：15/15 通过
```

`pytest -q` 另外 8 个用例全绿。

## 核心 API 速查

| 操作 | 写法 |
| --- | --- |
| 注册覆盖 | `app.dependency_overrides[原始函数] = 替身` |
| 清理全部 | `app.dependency_overrides.clear()` |
| 清理单个 | `del app.dependency_overrides[原始函数]` |
| 查看是否被覆盖 | `原始函数 in app.dependency_overrides` |
| 替身形式 | 普通函数、`lambda`、生成器都可以 |

| 实测 | 值 |
| --- | --- |
| 真实库列表 | 2 条 |
| 覆盖后列表 | 1 条假用户 |
| `/users/9` / `/users/1` | 200 / 404 |
| 假库新建 | `{"id":10,"name":"新用户"}` |
| 真实库 | 仍 `[1,2]` |
| 覆盖 `get_current_user` | `/me` 免令牌返回 `tester` |
| 覆盖 `get_settings` | `max_items=1` 生效 |
| 只覆盖 `get_db` | 嵌套 `get_repo` 自动跟随 |
| 覆盖前后 schema | 都是 4 条路径 |
| `clear()` 后 | 恢复 2 条 + 401 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| key 用字符串 | 覆盖静默失效 | 用函数对象 |
| 覆盖同名不同对象的函数 | 无效 | `import` 同一个对象 |
| 忘了 `clear()` | 污染后续用例 | `finally` 清理 |
| 每个用例都 `clear()` | 清掉别的 fixture | fixture 作用域内清 |
| 直接改模块全局数据 | 回滚麻烦 | 覆盖依赖 |
| 覆盖整个 `app` | 测不到真实路由 | 只覆盖数据层 |
| 假库缺 `next_id` | KeyError | 假库与真实库同构 |
| 以为覆盖会改 schema | 实际不变 | 放心 |
| 覆盖 `get_db` 后忘嵌套依赖 | 其实自动好了 | 只需覆盖最内层 |
| 用 `Mock` 替代函数 | 签名对不上 | 明确签名 |
| 覆盖成异步函数测同步依赖 | 报错 | 类型匹配 |
| 覆盖 `get_settings` 但缓存了 | 读到旧值 | 清缓存 |
| 在 `conftest.py` 里忘了 teardown | 跨文件污染 | `yield` + `clear` |
| 覆盖后断言真实库 | 数据在假库里 | 断言响应体 |
| 覆盖后测 422 失败 | 校验是真的，别绕过 | 保留真路由 |
| 多个 fixture 抢着覆盖 | 后覆盖先 | 分层 fixture |
| 覆盖后后台任务还用真库 | 任务捕获了原函数 | 传依赖进来 |
| 用 `dependency_overrides` 做生产开关 | 全局可变状态 | 用配置 |

## 毕业自查

- [ ] 能写覆盖 + 清理的 fixture
- [ ] 能解释为什么只覆盖 `get_db` 就够
- [ ] 能证明假库不污染真库
- [ ] 能覆盖配置与鉴权
- [ ] 知道覆盖不影响 schema
- [ ] 动手题一：写一个「假库 + 假时钟」的双覆盖 fixture
- [ ] 动手题二：把 `clear()` 换成精确 `del`，对比差异

> 想看 `dependency_overrides` 的查找顺序、`use_cache` 交互、覆盖生成器依赖的清理语义、`conftest.py` 分层、18 条坑，继续读 [`base.md`](./base.md)。