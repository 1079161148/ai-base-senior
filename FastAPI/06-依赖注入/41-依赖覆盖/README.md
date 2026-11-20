# 41 依赖覆盖

## 一句话结论

`app.dependency_overrides[原依赖] = 替身` 只认**可调用对象本身**（实测：另一个同名函数作 key 完全不生效）。覆盖后原依赖 0 次执行（实测 `REAL_CALLS == []`），嵌套依赖自动跟着换，鉴权可以绕过，替身自己的参数照样解析并被校验，OpenAPI 完全不变（实测前后 schema 相等）。覆盖只作用于当前 app，测试结束必须清理。

学完这一章，你能：在测试里把数据库/时钟/鉴权换成替身，且不污染其他用例。

## 最小可运行案例

```python
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI

app = FastAPI()


def get_db() -> Iterator[dict[str, str]]:
    yield {"source": "real-db"}


@app.get("/items")
def items(db: Annotated[dict[str, str], Depends(get_db)]) -> dict[str, Any]:
    return {"source": db["source"]}


# 测试里
def fake_db() -> Iterator[dict[str, str]]:
    yield {"source": "fake-db"}


app.dependency_overrides[get_db] = fake_db
assert app  # 现在 /items 返回 fake-db
app.dependency_overrides.clear()
```

完整版本（覆盖鉴权、类依赖、嵌套依赖、OpenAPI 不变）见 `examples/main.py` 与 `examples/verify.py`。

## 怎么跑

```powershell
cd "06-依赖注入\41-依赖覆盖\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 真实依赖 -> source=real-db, REAL_CALLS=['open', 'close']
[PASS] 覆盖函数 -> source=fake-db，真实依赖 0 次调用
[PASS] 覆盖嵌套依赖 -> 嵌套依赖也换了
[PASS] clear 恢复 -> clear() 后恢复 real-db
[PASS] 覆盖鉴权 -> 401 → 200（token=test-token）
[PASS] 覆盖类依赖 -> Clock → FakeClock
[PASS] key 是对象 -> 同名函数作 key 不生效（对象不同）
[PASS] 不影响 OpenAPI -> schema 完全一致
[PASS] 替身参数被解析 -> 替身的 y 参数生效且被校验
[PASS] 只影响本 app -> 其他 app 不受影响
[PASS] 非生成器替身 -> 非生成器替身可用

结果：11/11 通过
```

## 核心 API 速查

| 操作 | 写法 |
| --- | --- |
| 覆盖 | `app.dependency_overrides[real] = fake` |
| 恢复单个 | `del app.dependency_overrides[real]` |
| 全部恢复 | `app.dependency_overrides.clear()` |
| 在测试中隔离 | `try/finally` 或 pytest fixture |

| 实测行为 | 结果 |
| --- | --- |
| 覆盖后原依赖 | **0 次**执行 |
| 嵌套依赖 | 自动换成替身 |
| key 匹配 | 按对象身份，同名函数无效 |
| 类依赖 | key 是类对象 |
| 替身参数 | 照样进 OpenAPI、照样校验（422 生效）|
| OpenAPI | 前后 schema 完全一致 |
| 作用域 | 仅当前 `app` |
| 替身类型 | 生成器/普通函数均可 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用同名字符串/函数作 key | 不生效 | 用同一对象 |
| 忘了清理 | 污染后续测试 | fixture + `clear()` |
| 在模块顶层永久覆盖 | 生产也变 fake | 只在测试里 |
| 以为会改 OpenAPI | 文档不变（这是好事）| 别指望它改文档 |
| 替身签名与真实差异大 | 测试掩盖 bug | 保持接口一致 |
| 覆盖 `yield` 依赖的父依赖 | 子依赖仍走真实 | 覆盖真正被 `Depends` 的对象 |
| 多处覆盖同一 key | 后者覆盖前者 | 明确一处 |
| 在 `app.include_router` 前覆盖 | 仍生效（按对象匹配）| 但建议统一在 fixture |
| 覆盖后仍断言真实调用次数 | 期望错 | 断言 `== []` |
| 用覆盖跳过鉴权做生产开关 | 危险 | 只在测试 |

## 毕业自查

- [ ] 能写出 `dependency_overrides[real] = fake`
- [ ] 能解释为什么同名函数不行
- [ ] 能覆盖类依赖
- [ ] 能覆盖嵌套依赖的子节点
- [ ] 能说明覆盖不改 OpenAPI
- [ ] 能手写 fixture 保证隔离
- [ ] 动手题一：给项目加 `pytest` fixture 自动清理覆盖
- [ ] 动手题二：用覆盖测试「数据库超时」分支

> 想看覆盖的查找时机（每次请求查 `dependency_overrides`）、与缓存的关系、pytest fixture 模板、18 条坑，继续读 [`base.md`](./base.md)。