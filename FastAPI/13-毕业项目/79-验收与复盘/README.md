# 79 毕业项目（三）：验收与复盘

## 一句话结论

验收不是「再点一遍 /docs」，而是**79 条可执行断言分七个维度全绿**。本章的 `verify.py` 不复制业务代码，`sys.path` 直接指向第 78 章的 `examples/`——改了 78 章，这里立刻红。实测 79/79 通过，性能烟测 100 次 GET **P95 4.76ms / 总 366ms**。七个维度的划分本身就是复盘结论：业务(20) 最容易写，**错误契约(12) 与鉴权安全(15) 才是真正决定能不能上线的部分**，而「代码卫生(6)」靠人工 review 一定会漏，必须做成脚本。

## 最小可运行案例

```python
"""验收脚本的骨架：跨章引用 + 环境变量先设 + 逐条断言。"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
PROJECT = HERE.parent.parent / "78-生产化改造" / "examples"   # 验收目标
sys.path.insert(0, str(PROJECT))

# 【要点】必须先设环境变量，再 import main
os.environ["APP_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "accept.db")
os.environ["APP_TOKEN"] = "accept-token"
os.environ["APP_ENV"] = "test"

import main
from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer accept-token"}
BASE = "/api/v1/todos"

CASES = [
    ("A01", "创建 201", lambda c: c.post(BASE, json={"title": "x"}, headers=AUTH).status_code == 201),
    ("B01", "404 code", lambda c: c.get(f"{BASE}/999").json()["error"]["code"] == "not_found"),
    ("C01", "POST 需令牌", lambda c: c.post(BASE, json={"title": "x"}).status_code == 401),
]

with TestClient(main.app, raise_server_exceptions=False) as client:
    failures = 0
    for code, title, check in CASES:
        try:
            assert check(client)
            print(f"[PASS] {code} {title}")
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {code} {title} -> {exc}")
    print(f"\n结果：{len(CASES) - failures}/{len(CASES)} 通过")
```

## 怎么跑

```powershell
cd "13-毕业项目\79-验收与复盘\examples"
uv sync
uv run python verify.py
```

预期输出（节选）：

```text
[PASS] A01 创建 201 -> 201
[PASS] A10 pages 向上取整 -> ceil(3/2)=2
[PASS] B12 500 无堆栈 -> 无堆栈/无文案
[PASS] C08 默认令牌失效 -> demo-token 失效
[PASS] C14 日志无令牌 -> 1 条日志无令牌
[PASS] D04 回滚行数不变 -> 1 → 1
[PASS] F04 非法 env 启动失败 -> literal_error
[PASS] G06 响应已声明 -> 响应已声明

[性能] 100 次 / P95 4.76ms / 总 366ms
结果：79/79 通过
```

## 79 条验收清单

### A 业务正确性（20）

| 编号 | 断言 | 实测 |
| --- | --- | --- |
| A01 | 创建返回 201 | 201 |
| A02 | 创建带 `Location` | `/api/v1/todos/1` |
| A03 | 创建 body 5 字段 | id/title/done/priority/created_at |
| A04 | 默认 `priority=medium` | medium |
| A05 | 默认 `done=false` | false |
| A06 | 分页信封 5 键 | 5 键 |
| A07 | `total` 正确 | 3 |
| A08 | 首页 2 条 | 2 条 |
| A09 | 第二页 1 条 | 1 条 |
| A10 | `pages` 向上取整 | 2 |
| A11 | 越界页空列表 | `[]` |
| A12 | 越界页 `total` 不变 | 3 |
| A13 | 过滤 `done=true` | id=1 |
| A14 | 过滤 `done=false` | id=2,3 |
| A15 | 过滤 `priority` | id=1 |
| A16 | 过滤 `q` | id=2 |
| A17 | `q` 不区分大小写 | 命中 1 条 |
| A18 | 详情字段齐全 | 5 字段 |
| A19 | 部分更新只改 `done` | 仅 done |
| A20 | 删除后 404 | 204 → 404 |

### B 错误契约（12）

| 编号 | 断言 | 实测 |
| --- | --- | --- |
| B01 | 404 `code=not_found` | not_found |
| B02 | 404 message 含 id | 含 999 |
| B03 | 顶层只有 `error` | 仅 error |
| B04 | 401 `code=unauthorized` | unauthorized |
| B05 | 401 带 `WWW-Authenticate` | Bearer |
| B06 | 422 `code=validation_error` | validation_error |
| B07 | 422 `loc=body.title` | body.title |
| B08 | 422 `type=string_too_short` | string_too_short |
| B09 | `page=0` → 422 | 422 |
| B10 | `size=1001` → 422 | 422 |
| B11 | 500 `code=internal_error` | internal_error |
| B12 | 500 无堆栈/无内部文案 | 干净 |

### C 鉴权与安全（15）

| 编号 | 断言 | 实测 |
| --- | --- | --- |
| C01 | POST 无令牌 401 | 401 |
| C02 | PATCH 无令牌 401 | 401 |
| C03 | DELETE 无令牌 401 | 401 |
| C04 | 列表公开 | 200 |
| C05 | 详情公开 | 200 |
| C06 | 统计公开 | 200 |
| C07 | 错令牌 401 | 401 |
| C08 | 默认 `demo-token` 失效 | 401 |
| C09 | 响应无 `RuntimeError` | 干净 |
| C10 | 响应无内部消息 | 干净 |
| C11 | `/boom` 不进文档 | 不在 |
| C12 | `/_tx` 不进文档 | 不在 |
| C13 | `repr(settings)` 掩码 | 掩码 |
| C14 | 日志不含令牌 | 1 条日志无令牌 |
| C15 | 业务代码无硬编码令牌 | 仅 config |

### D 数据与事务（10）

| 编号 | 断言 | 实测 |
| --- | --- | --- |
| D01 | 创建落库 | 1 行 |
| D02 | 提交后仍在 | 仍在 |
| D03 | `/_tx` 返 409 | 409 |
| D04 | 回滚后行数不变 | 1 → 1 |
| D05 | 回滚无残留标题 | 无 |
| D06 | 更新持久化 | 已持久化 |
| D07 | 删除持久化 | 已删除 |
| D08 | id 连续自增 | 1,2,3 |
| D09 | 统计与库一致 | 3/1/2 |
| D10 | 空库统计 | 0 |

### E 可观测（8）

| 编号 | 断言 | 实测 |
| --- | --- | --- |
| E01 | 自动 8 位请求 ID | 8 位 |
| E02 | 请求 ID 透传 | trace-79 |
| E03 | `X-Elapsed-Ms` 可解析 | 可解析 |
| E04 | `X-App-Version` | 1.0.0 |
| E05 | 日志含 `method` | GET |
| E06 | 日志含 `path` | `/api/v1/todos` |
| E07 | 日志含 `status` | 200 |
| E08 | 日志含 `request_id` | 有 |

### F 配置与部署（8）

| 编号 | 断言 | 实测 |
| --- | --- | --- |
| F01 | 库路径来自 env | 来自 env |
| F02 | 令牌来自 env | 来自 env |
| F03 | env 来自 env | test |
| F04 | 非法 `APP_ENV` 启动失败 | `literal_error` |
| F05 | `/healthz` 200 | 200 |
| F06 | 探针不查库 | 不查 |
| F07 | `/docs` 200 | 200 |
| F08 | OpenAPI 4 条路径 | 4 条 |

### G 文档与代码卫生（6）

| 编号 | 断言 | 实测 |
| --- | --- | --- |
| G01 | 每个 operation 有 `summary` | 全有 |
| G02 | 每个 operation 有 `tags` | 全有 |
| G03 | 无裸 `except` | 10 文件干净 |
| G04 | SQL 全 `?` 占位 | 干净 |
| G05 | 无 `print(` 残留 | 干净 |
| G06 | 成功响应已声明（200/201/204） | 齐全 |

## 性能与安全复核

| 项 | 做法 | 实测 |
| --- | --- | --- |
| 吞吐烟测 | 100 次 GET 计时 | P95 4.76ms / 总 366ms |
| 信息泄露 | 搜响应体关键词 | 无 `Traceback`/`RuntimeError`/内部文案 |
| 密钥泄露 | 搜 `repr` 与日志记录 | 令牌不出现 |
| 注入面 | 搜 `%s`/`.format(`/`+` | 全 `?` 占位 |
| 内部端点 | 查 `openapi()` | `/boom`、`/_tx` 均不在 |
| 鉴权边界 | 逐端点验证 401/200 | 写保护、读公开 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 验收脚本复制一份业务代码 | 改了一边另一边不同步 | `sys.path` 指向目标 |
| 环境变量在 import 后设 | 配置是旧值 | import 前设 |
| 把验收脚本自己纳入扫描 | G 类永远红 | 排除 `verify.py` |
| 只验 happy path | 79 条全是 200 | 每维度都要反面 |
| 断言响应全文 | 加字段就红 | 断关键键 |
| 只测 4xx 不测 500 | 泄露无感知 | 强制 500 用例 |
| 性能只看平均 | 长尾被掩盖 | 看 P95 |
| 安全只靠 review | 漏一处就上线 | 做成脚本 |
| 用例之间共享数据 | 79 条互相污染 | 每条前 `reset_db()` |
| 断言日志总条数 | 加日志就红 | 断「有没有」 |
| 把 `204` 当失败 | G06 误报 | 允许 200/201/204 |
| 跨章路径写死 | 换目录就崩 | 相对 `HERE` 推导 |
| 临时库不清理 | 磁盘残留 | `shutil.rmtree` |
| 只跑一次就毕业 | 后续回归无保障 | 纳入 CI |

## 毕业自查

- [ ] 79 条全绿
- [ ] 能说出七个维度各自防什么
- [ ] 能证明「验收目标是 78 章产物」而不是复制
- [ ] 能复现性能烟测与安全扫描
- [ ] 能解释为什么 G 类必须脚本化
- [ ] 动手题一：加一条 A21「`PATCH` 空 body 返回原值」
- [ ] 动手题二：把性能烟测改成 500 次并输出 P99

> 想看 79 条的设计原则、「可执行验收」与「人工 review」的边界、跨章引用的坑、18 条坑，继续读 [`base.md`](./base.md)；项目级复盘见 [`REVIEW.md`](./REVIEW.md)。