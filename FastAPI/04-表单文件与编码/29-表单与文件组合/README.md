# 29 表单 + 文件组合

## 一句话结论

一个 `multipart/form-data` 请求里可以同时放普通字段和多个文件：`list[UploadFile]` 接同名 part 的多次出现，`UploadFile | None = None` 接可选文件，`list[UploadFile] = []` 接可选多文件。顺序与发送顺序一致（实测），单文件传给列表会自动变成 1 项。数量上限 FastAPI 不管，自己判（本例超出返 413）。

学完这一章，你能：一次请求传「说明 + 封面 + 多个附件」、区分「必填/可选/可多」、给文件数设限、看懂 OpenAPI 的 array schema。

## 最小可运行案例

```python
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

app = FastAPI()


@app.post("/upload/many")
async def upload_many(
    files: Annotated[list[UploadFile], File()],
    note: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    infos = []
    for file in files:
        data = await file.read()
        infos.append({"filename": file.filename, "size": len(data)})
    return {"count": len(files), "note": note, "files": infos}


@app.post("/upload/mixed")
async def upload_mixed(
    title: Annotated[str, Form(min_length=1)],
    cover: Annotated[UploadFile, File()],
    attachments: Annotated[list[UploadFile], File()] = [],
) -> dict[str, Any]:
    return {"title": title, "cover": cover.filename, "attachments": [a.filename for a in attachments]}
```

调用方式：

```python
files = [
    ("cover", ("cover.png", b"PNG", "image/png")),
    ("attachments", ("a.pdf", b"PDF1", "application/pdf")),
    ("attachments", ("b.pdf", b"PDF22", "application/pdf")),
]
client.post("/upload/mixed", files=files, data={"title": "季度报告"})
```

完整版本（数量限制、`list[bytes]`、OpenAPI 断言）见 `examples/main.py`。

## 怎么跑

```powershell
cd "04-表单文件与编码\29-表单与文件组合\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 多文件 + 备注 -> 3 个文件顺序与大小正确
[PASS] 多文件缺失 422 -> loc=['body', 'files']
[PASS] 单文件给 list -> 单文件 → count=1（不报错）
[PASS] 可选文件不传 -> file=None
[PASS] 可选文件传了 -> file.size=5
[PASS] 混合三者 -> 封面 3 字节 + 2 个附件
[PASS] 无附件默认空 -> attachments=[]
[PASS] 缺普通字段 -> title 缺失 422
[PASS] 文件数超限 -> 4 个 → 413
[PASS] 文件数刚好 -> sizes=[1,2,3]
[PASS] list[bytes] -> sizes=[2,3]
[PASS] OpenAPI array -> files.type=array, items.contentMediaType=application/octet-stream

结果：12/12 通过
```

## 核心 API 速查

| 需求 | 声明 | 不传时 |
| --- | --- | --- |
| 必填多文件 | `Annotated[list[UploadFile], File()]` | 422 `missing` |
| 可选单文件 | `Annotated[UploadFile \| None, File()] = None` | `None` |
| 可选多文件 | `Annotated[list[UploadFile], File()] = []` | `[]` |
| 小文件批量 | `Annotated[list[bytes], File()]` | 422 |
| 普通字段 | `Annotated[str, Form()]` | 422 |
| 可选字段 | `Annotated[str \| None, Form()] = None` | `None` |

| 实测行为 | 结果 |
| --- | --- |
| 3 个同名 `files` part | `count=3`，顺序保持 |
| 单文件给 `list[UploadFile]` | `count=1`，不报错 |
| 传 4 个给上限 3 的端点 | 应用层 413 |
| `attachments` 缺省 | `[]` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为 `list[UploadFile]` 默认为 `[]` | 不传就 422 | 显式 `= []` |
| 想限制文件数却指望框架 | 没有该参数 | 自己判，返回 413/422 |
| 循环里不 `await file.read()` | 拿到的是对象不是内容 | 每个文件都要读 |
| 把文件名当唯一键 | 重名覆盖 | 加索引/UUID |
| 一次传上百个小文件 | 内存 + 磁盘压力 | 限制数量与总大小 |
| 用 `list[bytes]` 传大文件 | OOM | `list[UploadFile]` |
| 混合端点再写 JSON 模型 | 模型传不进去（第 27 章）| 全用 Form/File |
| 以为多文件字段名可以不同 | 不同名要多个参数 | 同名 part 才对 list |
| 不区分 413 与 422 | 客户端重试策略错 | 413 不可重试，422 可改参数 |
| 忽略 `note` 等字段的长度 | 脏数据 | `Form(min_length=, max_length=)` |

## 毕业自查

- [ ] 能写出「字段 + 必填文件 + 可选多文件」
- [ ] 能说出三种「可选」声明与不传时的结果
- [ ] 能说出单文件传给 `list` 的行为
- [ ] 能给文件数设限并选对状态码
- [ ] 能解释 OpenAPI 里为什么是 `array`
- [ ] 能说出 `list[bytes]` 的风险
- [ ] 动手题一：给多文件加上「总大小不超过 5MB」的限制
- [ ] 动手题二：返回每个文件的 SHA-256，验证同一文件哈希一致

> 想看 multipart 报文里多个 part 的结构、顺序保证、数量与总量限制、18 条坑，继续读 [`base.md`](./base.md)。