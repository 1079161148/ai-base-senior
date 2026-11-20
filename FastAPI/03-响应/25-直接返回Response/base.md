# 25 直接返回 Response · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「什么时候必须放弃响应模型、文件与流式的头规则、307/302 的差别、中文文件名编码、路径穿越防护」拆开。学完这章，你要能在「有模型」和「纯字节」之间做对选择。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 21–24 章（响应模型、状态码、联合类型、响应头） |
| 覆盖范围 | `FileResponse`、`StreamingResponse`、`RedirectResponse`、`response_class`、自定义 `Response` |
| 明确不覆盖 | 静态文件挂载（第 52 章）、Range 深入、断点续传实现细节、后台任务（M08） |
| 学完验收 | 能跑通 `verify.py` 11/11、能解释 307 默认、能处理中文文件名、能防路径穿越 |

## 0. 怎么用这份文件

**依据约定**：`` `[Dn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 何时该放弃响应模型
2 机制（第 2 节）    → 返回值分派规则
3 API（第 3 节）     → 五类 Response 逐个拆
4 边界（第 4 节）    → Range、中文名、路径穿越、流式错误
5 注意事项（第 5 节）→ 20 条对照
6 最佳实践（第 6 节）→ 下载与导出模板
```

## 1. 概念：三种「响应形态」

| 形态 | 例子 | 用什么 |
| --- | --- | --- |
| 结构化数据 | JSON 对象/列表 | 响应模型 |
| 单块字节 | 文件、XML、CSV | `FileResponse`/`Response` |
| 连续字节 | 大导出、SSE、日志流 | `StreamingResponse` |

判断标准：**客户端能否整体接收**。能 → 单块；不能 → 流式。

## 2. 机制：返回值分派

```text
函数返回
 ├── Response 实例（含子类） → 直接发送（跳过 response_model）
 ├── 模型/dict → 响应模型校验 → 序列化 → JSONResponse
 └── None + 204 → 空响应
```

| 事实 | 含义 |
| --- | --- |
| `Response` 子类直接发送 | 不校验、不过滤、不写 OpenAPI schema |
| `response_class=` 只换默认类 | 返回模型时用该类序列化 |
| `StreamingResponse` 一旦开始 yield | 头已发送，状态码不可改 |

## 3. API 逐个拆解

### 3.1 `FileResponse`

```python
return FileResponse(path, filename="报告.txt", media_type="application/octet-stream")
```

| 行为 | 实测 |
| --- | --- |
| `Content-Type` | 按扩展名推断（`.txt` → `text/plain; charset=utf-8`）|
| `Content-Length` | 自动填 |
| `Content-Disposition` | ASCII 名 → `filename="hello.txt"`；中文 → `filename*=utf-8''%E6%8A%A5%E5%91%8A.txt` |
| Range | Starlette 支持（本章未断言 206）|
| 文件不存在 | 由你判（`HTTPException(404)`），否则 500 |

### 3.2 `StreamingResponse`

```python
return StreamingResponse(gen(), media_type="text/plain")
```

| 行为 | 实测 |
| --- | --- |
| `Content-Length` | **没有**（chunked）|
| 内容顺序 | 按 yield 顺序拼接 |
| 中途异常 | 已发出的部分保留，状态码仍是 200 |
| 生成器类型 | 同步/异步生成器均可 |

### 3.3 `RedirectResponse`

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `status_code` | **307** | 保持方法（POST → POST）|
| `headers` | 无 | 可加 `Location` 之外的头 |
| `Location` | 自动 | 由 `url` 参数 |

307 vs 302：

| 码 | 方法 | 典型场景 |
| --- | --- | --- |
| 301 | 永久，GET | SEO 迁移 |
| 302 | 临时，可能被改为 GET | 传统临时跳转 |
| 307 | 临时，保持方法 | **默认**，API 跳转更安全 |
| 308 | 永久，保持方法 | 永久迁移 |

### 3.4 `response_class`

| 作用 | 说明 |
| --- | --- |
| 改真实媒体类型 | 返回 `str` 时用该类 |
| 改 OpenAPI `content` | 实测 `text/plain` 出现在 schema |
| 与 `response_model` 共存 | 模型序列化后仍用该类（JSON 场景少见）|

### 3.5 自定义 `Response` 子类

```python
class XmlResponse(Response):
    media_type = "application/xml"
```

| 优点 | 说明 |
| --- | --- |
| 复用媒体类型 | 不用每次传 |
| 可封装序列化 | `render()` 里统一处理 |
| 类型注解可读 | `-> XmlResponse` |

## 4. 边界条件

### 4.1 Range 与断点续传

`FileResponse` 支持 `Range: bytes=0-99` → 206。本章**未断言**具体行为，生产环境（如视频、大文件）需要专门验证反向代理是否也支持。

### 4.2 中文文件名

实测：`FileResponse(path, filename="报告.txt")` 生成

```text
Content-Disposition: attachment; filename*=utf-8''%E6%8A%A5%E5%91%8A.txt
```

| 事实 | 说明 |
| --- | --- |
| 走 RFC 5987 | `filename*=utf-8''<pct-encoded>` |
| 不要手拼 | 手拼会漏编码或半角引号错误 |
| 老客户端 | 可能不认 `filename*`，可同时给 ASCII 回退名 |

### 4.3 路径穿越（必须防）

```python
path = ASSETS / filename       # filename="../../etc/passwd" 会逃出目录
```

| 防护 | 做法 |
| --- | --- |
| 白名单 | 只允许数据库里存在的文件名 |
| 规范化校验 | `(ASSETS / filename).resolve().is_relative_to(ASSETS.resolve())` |
| 只取 basename | `Path(filename).name` |
| 重命名存储 | 用 UUID 存盘，展示名单独存 |

本章示例**故意未做**防护，并在 docstring 标注——真实项目必须补。

### 4.4 流式的三件事

| 问题 | 说明 |
| --- | --- |
| 错误处理 | 开始 yield 后无法改状态码，尽量先校验再流 |
| 背压 | 客户端慢会阻塞生成器（同步生成器会占线程）|
| 超时 | 反代常有 60s 空闲超时，长任务要心跳 |

### 4.5 大文件不要做的事

| 反模式 | 后果 |
| --- | --- |
| `path.read_bytes()` 后返回 | 全量进内存，OOM |
| 用 `Response(content=big_string)` | 同上 |
| 多次 `FileResponse` 打开同一文件 | 句柄压力 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `response_model` + 返回 `Response` | 文档骗人 | 去掉模型 | 实测 |
| 以为 `RedirectResponse` 是 302 | 实际 307 | 显式传 302 | 实测 |
| 307 用于 POST 跳转 | 方法被保留，可能重复提交 | 按语义选 302/303 | `[D2]` |
| 大文件读进内存 | OOM | `FileResponse`/流式 | `[D1]` |
| 流式中途抛错想 500 | 头已发 | 先校验 | 实测 |
| 文件名直接拼路径 | 路径穿越 | 白名单/resolve 校验 | `[D4]` |
| 手拼 `Content-Disposition` | 中文乱码 | 交给框架 | 实测 |
| 用 `response_class` 却没改返回类型 | 媒体类型不符 | 返回对应内容 | 实测 |
| 流式里同步 sleep 重活 | 阻塞事件循环 | 异步/线程池 | `[D3]` |
| 忘了 `media_type` | 客户端按默认解析 | 显式指定 | `[D1]` |
| 用 `PlainTextResponse` 返回 JSON 字符串 | 客户端不解析 JSON | `JSONResponse` | `[D1]` |
| `FileResponse` 不判存在 | 500 | 404 | 实测 |
| 直接返回 `open()` 的文件对象 | 不确定行为 | 用 `FileResponse` | `[D1]` |
| 流式响应做压缩 | 双重编码风险 | 交给反代 | 第 52 章 |
| 用 `RedirectResponse` 传用户输入 URL | 开放重定向 | 白名单 | `[D4]` |
| 大 CSV 一次性生成 | 内存爆 | 流式逐行 | `[D3]` |
| 下载不设文件名 | 浏览器用 URL 末段 | 传 `filename` | `[D1]` |
| `Content-Disposition: inline` 与 `attachment` 混用 | 体验不一致 | 按场景固定 | `[D2]` |
| 流式响应不设超时 | 连接挂死 | 反代/客户端超时 | `[D3]` |
| 只测小文件 | 大文件问题上线才发现 | 加 10MB 用例 | 第 71 章 |
| 用 `StreamingResponse` 返回一个 JSON 数组 | 客户端无法增量解析 | 用 NDJSON（每行一个对象）| `[D3]` |

## 6. 最佳实践与编码建议

### 6.1 安全下载模板

```python
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()
BASE = Path(__file__).parent / "assets"


@app.get("/files/{name}")
def get_file(name: str) -> FileResponse:
    safe = Path(name).name                      # 去掉任何目录成分
    path = (BASE / safe).resolve()
    if not path.is_relative_to(BASE.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=safe)
```

### 6.2 流式导出模板

```python
import asyncio
from typing import AsyncIterator

from fastapi.responses import StreamingResponse


@app.get("/export")
async def export() -> StreamingResponse:
    async def rows() -> AsyncIterator[str]:
        yield "id,name\n"
        for i in range(1000):
            yield f"{i},name-{i}\n"
            if i % 100 == 0:
                await asyncio.sleep(0)          # 让出事件循环

    return StreamingResponse(rows(), media_type="text/csv")
```

### 6.3 编码建议

| 建议 | 说明 |
| --- | --- |
| 下载一律走 `FileResponse` | 自动长度与类型 |
| 大导出走流式 | 控制内存 |
| 重定向显式写码 | 别依赖默认 |
| 文件名只取 basename | 防穿越 |
| 流式前完成全部校验 | 头不可撤回 |
| 媒体类型显式 | 别让客户端猜 |

### 6.3 选型速查

| 需求 | 选择 |
| --- | --- |
| JSON | 响应模型 |
| 单文件下载 | `FileResponse` |
| 大 CSV/日志 | `StreamingResponse` |
| 跳转 | `RedirectResponse` |
| XML | 自定义 `Response` |
| HTML 页面 | `HTMLResponse` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[D1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/custom-response/ | 各类 Response 用法 |
| `[D2]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15.4 | 3xx 语义与 307 |
| `[D3]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/custom-response/#streamingresponse | 流式响应 |
| `[D4]` | 安全指南 | https://owasp.org/www-community/attacks/Path_Traversal | 路径穿越与开放重定向 |

> **核对状态**：`[D1]`–`[D4]` 为官方/规范链接，**本次未逐页直连复核**；文件头、307 默认、流式无 `Content-Length`、中文名 RFC 5987、模型被绕过均为本机实测，`examples/verify.py` 复现 11/11 通过。Range/206 **未断言**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三种响应形态与选择标准
- [ ] `Response` 子类为什么跳过响应模型
- [ ] 307 与 302 的差别
- [ ] 中文文件名为什么要编码
- [ ] 流式为什么没有 `Content-Length`

**能写出（代码层）**：

- [ ] `FileResponse` 下载
- [ ] `StreamingResponse` 流式
- [ ] `RedirectResponse` 带码
- [ ] `response_class` 换类型
- [ ] 自定义 `Response` 子类

**能判断（避坑层）**：

- [ ] 看到路径直接拼接 → 指出穿越
- [ ] 看到大文件读进内存 → 指出 OOM
- [ ] 看到流式中抛错想 500 → 指出头已发
- [ ] 看到开放重定向 → 指出白名单
- [ ] 看到 `response_model` + `Response` → 指出文档骗人

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] 浏览器下载中文名文件不乱码
- [ ] `curl -i` 看 `Content-Disposition` 与 `Transfer-Encoding`

## 9. 下一章衔接

第 26 章 `OpenAPI 文档定制`：本章的 `response_class`、`responses=` 都在改文档。下一章系统讲 `title`/`description`/`tags`/`summary`/`deprecated`/`openapi_extra`，以及如何把「文档」当成对外契约来维护。

本章留下的伏笔：

1. 静态文件挂载在 第 52 章。
2. 压缩与缓存头在 第 52 章。
3. 后台任务与 202 在 M08。
4. 大文件上传在 M04。
