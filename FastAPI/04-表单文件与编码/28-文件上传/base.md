# 28 文件上传 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「multipart 报文怎么被解析、`UploadFile` 的内存与落盘、读流的两个陷阱、文件名与类型的可信边界、上传安全的完整清单」拆开。学完这章，你要能写出「不会被 10GB 文件打挂」的上传端点。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.10.0 / python-multipart 0.0.34（本机实测） |
| 前置 | 第 27 章（Form） |
| 覆盖范围 | `File()`、`UploadFile`、`bytes`、分块读、`SpooledTemporaryFile`、文件名与类型可信性 |
| 明确不覆盖 | 多文件与混合字段（第 29 章）、对象存储上传、断点续传、病毒扫描 |
| 学完验收 | 能跑通 `verify.py` 12/12、能解释落盘阈值、能说出三种大小限制手段 |

## 0. 怎么用这份文件

**依据约定**：`` `[Un]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 文件为什么不能走 JSON
2 机制（第 2 节）    → multipart 解析与内存/磁盘
3 API（第 3 节）     → UploadFile / bytes / 流式方法
4 边界（第 4 节）    → 阈值、大小限制、文件名、类型、清理
5 注意事项（第 5 节）→ 19 条对照
6 最佳实践（第 6 节）→ 安全上传模板
```

## 1. 概念：文件是「二进制 + 元数据」，不是 JSON 字段

| 事实 | 含义 |
| --- | --- |
| JSON 不能直接放二进制 | 要 base64，体积涨 33% 且要全量解码 |
| `multipart/form-data` 每部分自带头 | 可以有多个文件 + 普通字段（第 29 章）|
| 文件内容不进 Python 内存（用 `UploadFile`）| 大文件才不会 OOM |

## 2. 机制：multipart 从字节到对象

```text
请求体（boundary 分隔）
  → python-multipart 解析出多个 part
  → 文件 part → SpooledTemporaryFile（≤1MB 内存，>1MB 落盘）
  → 包装成 starlette.datastructures.UploadFile
  → 注入参数（失败：422）
```

| 事实 | 说明 |
| --- | --- |
| `UploadFile.file` 是 `SpooledTemporaryFile(max_size=1024*1024)` | 实测 1MB+1 字节触发落盘 |
| `filename` / `content_type` 来自 part 头 | 客户端完全可控 |
| 未声明的文件 part | 忽略 |
| 缺必填文件 | 422，`loc=["body","file"]` |

## 3. API 逐个拆解

### 3.1 `UploadFile`（推荐）

| 方法 | 行为 |
| --- | --- |
| `await read()` | 读全部（可能很大）|
| `await read(n)` | 读 n 字节 |
| `await seek(0)` | 回开头（可重读）|
| `await close()` | 关闭临时文件 |
| `await write(b)` | 写入（一般不用）|

实测：读完再读得到 `b""`——这是流语义，不是 bug。

### 3.2 `bytes`

```python
def upload(data: Annotated[bytes, File()]) -> dict[str, int]:
```

| 优点 | 缺点 |
| --- | --- |
| 写法最短 | 全量进内存 |
| 无异步 | 大文件阻塞 |

### 3.3 `File()` 的元数据

| 参数 | 作用 |
| --- | --- |
| `description` | OpenAPI 说明 |
| `alias` | part 名 |
| `media_type` | 文档里的媒体类型提示 |
| `deprecated` | 文档标记 |

`File()` 不负责「校验文件类型」，别指望它。

### 3.4 OpenAPI 形态（实测）

```json
{"type": "string", "contentMediaType": "application/octet-stream", "title": "File"}
```

| 版本差异 | 说明 |
| --- | --- |
| 旧文档常见 `format: binary` | 部分 SDK 生成器仍按它处理 |
| 本机 0.146 生成 `contentMediaType` | 断言时两者都要兼容 |

## 4. 边界条件

### 4.1 落盘阈值（实测）

| 大小 | `_rolled` |
| --- | --- |
| 5 字节 | `False` |
| 1024×1024+1 字节 | `True` |

`_rolled` 是 CPython 私有属性，只用于教学；业务代码不要判断它。

### 4.2 大小限制的三种做法

| 层次 | 做法 | 说明 |
| --- | --- | --- |
| 反代 | nginx `client_max_body_size 10m` | **最有效**，先挡住 |
| 应用层 | 读 `file.size` 或分块累计超限即拒 | 避免读完才发现 |
| 服务器 | uvicorn 限制（视实现）| 不如反代可靠 |

本章**未实测** FastAPI 是否支持对 `File()` 直接传 `max_length` 做硬限制，写代码时请按你所装版本验证；稳妥做法是反代 + 分块累计。

### 4.3 文件名不可信（实测）

```python
client.post("/upload", files={"file": ("../../etc/passwd", b"x", "text/plain")})
```

服务端收到 `filename="../../etc/passwd"`。只 `Path(name).name` 还不够（`..`、空名、超长名、Windows 保留名 `CON`），完整做法：

| 步骤 | 做法 |
| --- | --- |
| 1 清洗 | `Path(name).name`，拒绝空/超 255 字符 |
| 2 重命名 | 存储用 UUID，展示名单独存库 |
| 3 目录隔离 | 存到非 Web 根目录，按内容哈希分桶 |
| 4 类型校验 | 扩展名白名单 + 内容嗅探（如 `imghdr` 已弃用，用 `filetype` 类库或魔法字节）|

### 4.4 content_type 不可信（实测）

客户端声明 `text/html` 就收到 `text/html`。用 `content_type` 决定「是否放行」等于把安全交给客户端。

### 4.5 临时文件清理

| 情况 | 行为 |
| --- | --- |
| 正常返回 | Starlette 在请求结束时关闭 `UploadFile`（多数情况）|
| 手动 `close()` | 立即释放 |
| 长任务持有 | 可能持续占磁盘，需显式管理 |

### 4.6 内存/磁盘算一笔账

| 并发 | 每文件 | `bytes` 内存 | `UploadFile` |
| --- | --- | --- | --- |
| 10 | 10MB | 100MB | 0（全落盘）|
| 100 | 10MB | 1GB | 少量内存 + 磁盘 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 大文件用 `bytes` | 内存爆 | `UploadFile` | 实测 |
| 读完再读期待还有内容 | `b""` | `seek(0)` | 实测 |
| 直接用 `filename` 存盘 | 路径穿越 | 清洗 + UUID | 实测 |
| 用 `content_type` 做安全判断 | 可伪造 | 内容嗅探 + 白名单 | 实测 |
| 不限制请求体大小 | 磁盘/内存耗尽 | 反代限制 | `[U3]` |
| 不关 `UploadFile` | 临时文件堆积 | `close()`/依赖 yield | `[U2]` |
| 断言 OpenAPI 只有 `format: binary` | 实测是 `contentMediaType` | 两者兼容 | 实测 |
| 同步函数里 `await file.read()` | 报错 | `async def` | `[U1]` |
| 用 `list[UploadFile]` 却单文件传 | 422 | 见第 29 章 | `[U4]` |
| 上传后原样回显文件名 | XSS（HTML 场景）| 转义或用 JSON | `[U5]` |
| 允许任意扩展名 | 上传 webshell | 白名单 | `[U5]` |
| 存到 Web 可执行目录 | 被直接执行 | 非 Web 根 + 权限 | `[U5]` |
| 用 `file.file.read()` 混着 `await file.read()` | 位置错乱 | 只选一种读法 | `[U2]` |
| 不校验空文件 | 下游报错 | 显式 `size > 0` | 实测 |
| 相信 `size` 等于实际写入字节 | 异常中断时不符 | 以实际读取为准 | `[U2]` |
| 上传接口无鉴权 | 任意人写盘 | 前置鉴权 | 第 44 章 |
| 文件名重复覆盖 | 数据丢失 | UUID/哈希命名 | `[U5]` |
| 不记录审计日志 | 无法追责 | 记录谁传了什么 | 第 50 章 |
| 只测小文件 | 大文件问题上线才发现 | 加 >1MB 与超限用例 | 第 71 章 |
| 只在应用层限大小 | 请求体已上传完才被拒，带宽被吃 | 反代也限 | `[U3]` |

## 6. 最佳实践与编码建议

### 6.1 安全上传模板

```python
import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from typing import Annotated

router = APIRouter(prefix="/files", tags=["文件"])

STORE = Path("var/uploads")          # 不在 Web 根目录
MAX_BYTES = 10 * 1024 * 1024
ALLOWED_EXT = {".txt", ".csv", ".png", ".jpg"}


@router.post("")
async def upload(file: Annotated[UploadFile, File()]) -> dict[str, str]:
    name = Path(file.filename or "").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=415, detail="不支持的文件类型")

    digest = hashlib.sha256()
    total = 0
    target = STORE / f"{uuid.uuid4().hex}{ext}"
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("wb") as out:
        while chunk := await file.read(64 * 1024):
            total += len(chunk)
            if total > MAX_BYTES:
                out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="文件过大")
            digest.update(chunk)
            out.write(chunk)

    return {"stored": target.name, "sha256": digest.hexdigest(), "size": str(total)}
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 默认 `UploadFile` | 除非确定很小 |
| 边读边算哈希/写盘 | 不二次读 |
| 大小在读取中判 | 不等读完 |
| 文件名清洗 + 重命名 | 双重 |
| 类型白名单 | 扩展名 + 内容 |
| 存非 Web 根目录 | 防执行 |
| 前后都限制大小 | 反代 + 应用 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 单文件 | `UploadFile` |
| 小配置文本 | `bytes` 也可 |
| 多文件 | `list[UploadFile]`（第 29 章）|
| 表单 + 文件 | `Form` + `File`（第 29 章）|
| 超大文件 | 直传对象存储（预签名 URL）|

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[U1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/request-files/ | `File`/`UploadFile` 用法 |
| `[U2]` | 官方文档 | https://www.starlette.io/requests/#request-files | `UploadFile` 与 SpooledTemporaryFile |
| `[U3]` | 参考 | https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size | 反代大小限制 |
| `[U4]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/request-forms-and-files/ | 多文件与混合 |
| `[U5]` | 安全指南 | https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload | 上传安全 |

> **核对状态**：`[U1]`–`[U5]` 为官方/安全链接，**本次未逐页直连复核**；上传、读取语义、1MB 落盘、文件名与 content_type 不可信、OpenAPI `contentMediaType` 均为本机实测（python-multipart 0.0.34），`examples/verify.py` 复现 12/12 通过。`File(max_length=...)` 硬限制**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 文件为什么不能走 JSON
- [ ] `UploadFile` 与 `bytes` 的内存差异
- [ ] 1MB 阈值与 `SpooledTemporaryFile`
- [ ] 读流语义（读完为空）
- [ ] 文件名与类型的可信边界
- [ ] 三种大小限制手段

**能写出（代码层）**：

- [ ] `UploadFile` 上传并返回 size
- [ ] 分块读 + 哈希
- [ ] `bytes` 简化版
- [ ] 文件名清洗
- [ ] 超限即拒

**能判断（避坑层）**：

- [ ] 看到大文件用 `bytes` → 指出 OOM
- [ ] 看到直接用 filename 存盘 → 指出穿越
- [ ] 看到用 content_type 放行 → 指出伪造
- [ ] 看到无大小限制 → 指出耗尽
- [ ] 看到只测小文件 → 指出漏测

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `/docs` 里上传一个文本文件
- [ ] 上传一个 >1MB 文件并观察落盘

## 9. 下一章衔接

第 29 章 `表单 + 文件组合`：`list[UploadFile]`、单值 `UploadFile | None`、文件与普通字段混用、`multipart` 里多个同名 part 的顺序、缺失文件的处理，以及「一个请求传多种资源」的建模方式。

本章留下的伏笔：

1. 多个同名文件在 第 29 章。
2. 对象存储直传在 M13。
3. 上传鉴权在 第 44 章。
4. 审计日志在 第 50 章。