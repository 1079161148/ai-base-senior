# 29 表单 + 文件组合 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「多个 part 怎么映射到参数、三种可选声明、数量与总量限制、顺序与重名、OpenAPI 的 array 结构」拆开。学完这章，你要能一次请求安全地收「说明 + 一批附件」。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.10.0 / python-multipart 0.0.34（本机实测） |
| 前置 | 第 27 章（Form）、第 28 章（文件上传） |
| 覆盖范围 | `list[UploadFile]`、`UploadFile \| None`、`list[...] = []`、混合字段、数量限制、OpenAPI array |
| 明确不覆盖 | 分片上传/断点续传、直传对象存储、压缩包解压 |
| 学完验收 | 能跑通 `verify.py` 12/12、能选对「可选」声明、能给出数量与总量限制方案 |

## 0. 怎么用这份文件

**依据约定**：`` `[Mn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 一个请求里多种 part
2 机制（第 2 节）    → part 名 → 参数名 → 列表
3 API（第 3 节）     → 三种可选 + 混合
4 边界（第 4 节）    → 数量、总量、顺序、重名
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 附件上传模板
```

## 1. 概念：multipart 是「一堆命名 part 的序列」

| part 名 | 内容 | 映射到 |
| --- | --- | --- |
| `title` | 文本 | `Form()` 参数 |
| `cover` | 一个文件 | `UploadFile` |
| `attachments` | 多个文件（同名重复） | `list[UploadFile]` |

关键：**列表靠「同名 part 出现多次」**，不靠 `attachments[0]` 这类下标写法。

## 2. 机制：从 part 到函数参数

```text
multipart 报文
  ├── title: "季度报告"            → Form 参数
  ├── cover: (filename, bytes)     → UploadFile
  ├── attachments: a.pdf           ┐
  └── attachments: b.pdf           ┴→ list[UploadFile]（按出现顺序）
```

| 事实 | 说明 |
| --- | --- |
| 列表顺序 = part 顺序（实测）| 可以依赖，但别把业务顺序建立在客户端发送顺序上 |
| 单文件给列表 | 变成 1 项（实测）|
| 未声明的 part | 忽略 |
| 缺必填 part | 422，`loc=["body", 名]` |
| 同名 part 但参数是单值 | 只取最后一个/第一个（未断言，避免依赖）|

## 3. API 逐个拆解

### 3.1 必填多文件

```python
files: Annotated[list[UploadFile], File()]
```

不传 → 422 `missing`（不是空列表）。

### 3.2 可选单文件

```python
file: Annotated[UploadFile | None, File()] = None
```

不传 → `None`，返回 200（实测）。

### 3.3 可选多文件

```python
attachments: Annotated[list[UploadFile], File()] = []
```

不传 → `[]`（实测）。FastAPI 对可变默认值有特殊处理，不会跨请求共享；但仍建议在函数内不要修改该列表。

### 3.4 与普通字段混用

| 组合 | 是否可行 |
| --- | --- |
| `Form` + `File` | ✅（本章）|
| `Form` + `File` + JSON 模型 | ❌ 模型会变成传不进去的 part（第 27 章）|
| 纯 `File` 无 `Form` | ✅ |

### 3.5 OpenAPI（实测）

```json
"files": {"type": "array",
          "items": {"type": "string", "contentMediaType": "application/octet-stream"}}
```

`/docs` 里显示为「可多选文件」控件。

## 4. 边界条件

### 4.1 数量限制

| 层次 | 手段 | 结果码建议 |
| --- | --- | --- |
| 应用层 | `len(files) > N` | 413（或 422，团队统一）|
| 反代 | 请求体总大小 | 413 |
| 网关 | 每请求 part 数（少见）| 400/413 |

实测：4 个文件 → 应用层 413。

### 4.2 总量限制

按文件逐个读、累计字节数，超限立即中止并清理已写文件（第 28 章模板）。不要先读完全部再判断。

### 4.3 顺序

实测保持发送顺序，但：

| 风险 | 说明 |
| --- | --- |
| 客户端并发发送 | 顺序由客户端库决定 |
| 业务含义依赖顺序 | 脆弱，改用显式 `index` 字段 |

### 4.4 重名文件

| 情况 | 处理 |
| --- | --- |
| 两个 part 同 filename | 各自独立，存储时 UUID 重命名 |
| 覆盖写 | 数据丢失 |

### 4.5 内存

| 声明 | 10 个 × 10MB |
| --- | --- |
| `list[UploadFile]` | 全部落盘，内存低 |
| `list[bytes]` | 100MB 常驻内存 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `list[UploadFile]` 期望默认空 | 不传就 422 | 显式 `= []` | 实测 |
| 用不同 part 名接多文件 | 参数对不上 | 同名 part | 实测 |
| 只取 `files[0]` | 其余被静默丢弃 | 遍历 | `[M1]` |
| 用列表长度做业务上限却不校验 | 可传 1000 个 | 显式限制 | 实测 |
| 先读全部再判大小 | 内存/磁盘先被占满 | 边读边判 | 第 28 章 |
| 混合端点写 JSON 模型 | 模型传不进去 | 全 Form/File | 第 27 章 |
| 以为多文件一定 422 | 单文件也合法 | 校验 `count` | 实测 |
| 用 `list[bytes]` 接大文件 | OOM | `list[UploadFile]` | 第 28 章 |
| 依赖 part 顺序做业务 | 顺序可能变 | 加 `index` 字段 | 实测 |
| 重名文件直接存 | 覆盖 | UUID 重命名 | `[M3]` |
| 不限制总量 | 磁盘打满 | 累计判断 | `[M2]` |
| 413 与 422 混用 | 客户端重试策略错 | 明确约定 | `[M2]` |
| 文件字段用 `Form()` 声明 | 类型不符 | `File()` | `[M1]` |
| 可选列表默认 `None` | 遍历时报错 | `= []` 或判空 | 实测 |
| 上传后不关文件 | 临时文件堆积 | `close()` | `[M1]` |
| 只测 1 个文件 | 多文件路径没覆盖 | 加 0/1/多/超限用例 | 第 71 章 |
| 忽略普通字段校验 | 脏标题入库 | `Form(min_length=)` | 第 27 章 |
| 在同步函数里 `await` | 报错 | `async def` | `[M1]` |
| 只 `await files[0].read()` | 其余文件未读，临时文件滞留 | 逐个读完或关闭 | `[M1]` |

## 6. 最佳实践与编码建议

### 6.1 附件上传模板

```python
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter(prefix="/posts", tags=["帖子"])

MAX_FILES = 5
MAX_TOTAL = 20 * 1024 * 1024


@router.post("")
async def create_post(
    title: Annotated[str, Form(min_length=1, max_length=100)],
    body: Annotated[str, Form(max_length=5000)],
    attachments: Annotated[list[UploadFile], File()] = [],
) -> dict[str, Any]:
    if len(attachments) > MAX_FILES:
        raise HTTPException(status_code=413, detail=f"最多 {MAX_FILES} 个附件")

    total = 0
    names: list[str] = []
    for item in attachments:
        while chunk := await item.read(64 * 1024):
            total += len(chunk)
            if total > MAX_TOTAL:
                raise HTTPException(status_code=413, detail="附件总大小超限")
        names.append(item.filename or "")

    return {"title": title, "attachments": names, "total": total}
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 列表默认 `= []` | 明确「可选」|
| 数量 + 总量双限制 | 缺一不可 |
| 边读边判 | 不二次读 |
| 顺序不承载业务 | 用 `index` |
| 重名重命名 | UUID |
| 统一 413 语义 | 客户端不重试 |

### 6.3 选型速查

| 需求 | 声明 |
| --- | --- |
| 必填一个 | `UploadFile` |
| 可选一个 | `UploadFile \| None = None` |
| 必填多个 | `list[UploadFile]` |
| 可选多个 | `list[UploadFile] = []` |
| 表单字段 | `Form()` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[M1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/request-forms-and-files/ | 表单与文件混用、多文件 |
| `[M2]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15.5.14 | 413 语义 |
| `[M3]` | 安全指南 | https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload | 上传安全 |

> **核对状态**：`[M1]`–`[M3]` 为官方/规范/安全链接，**本次未逐页直连复核**；多文件顺序、单文件给列表、三种可选声明、数量超限 413、OpenAPI array 均为本机实测，`examples/verify.py` 复现 12/12 通过。同名 part 给单值参数的行为**未断言**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] multipart 里「同名 part」如何变成列表
- [ ] 三种可选声明的差异
- [ ] 数量与总量两层限制
- [ ] 顺序能不能承载业务
- [ ] 重名文件的处理

**能写出（代码层）**：

- [ ] 字段 + 必填文件 + 可选多文件
- [ ] 可选单文件
- [ ] 数量限制 413
- [ ] 总量累计限制
- [ ] `list[bytes]` 小批量

**能判断（避坑层）**：

- [ ] 看到 `list` 无默认值 → 指出 422
- [ ] 看到 `list[bytes]` 大文件 → 指出 OOM
- [ ] 看到先读后判 → 指出占满
- [ ] 看到混合 JSON 模型 → 指出传不进去
- [ ] 看到依赖顺序 → 指出脆弱

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `/docs` 里多选文件上传
- [ ] 手工传 4 个文件触发 413

## 9. 下一章衔接

第 30 章 `jsonable_encoder`：文件与表单处理完，最终都要变成可 JSON 化的数据。下一章讲「为什么 `datetime`/`Decimal`/ORM 对象不能直接进 JSON、`jsonable_encoder` 怎么递归转换、什么时候用它、什么时候该用响应模型和自定义编码器」。

本章留下的伏笔：

1. 响应序列化在 第 21 章已讲模型层，第 30 章讲底层编码。
2. 对象存储直传在 M13。
3. 上传审计在 第 50 章。
4. 测试覆盖在 第 71 章。