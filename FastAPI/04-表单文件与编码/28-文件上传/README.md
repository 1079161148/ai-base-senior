# 28 文件上传（File / UploadFile）

## 一句话结论

文件走 `multipart/form-data`。小文件可以用 `bytes`，**大文件必须用 `UploadFile`**：它用 `SpooledTemporaryFile`，超过 1MB 自动落盘（实测 `_rolled` 由 `False` 变 `True`），不会把内存撑爆。`filename` 和 `content_type` 都是客户端说的，**不可信**。

学完这一章，你能：接上传、分块读、判断何时落盘、清洗文件名、识别「content_type 撒谎」。

## 最小可运行案例

```python
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, UploadFile

app = FastAPI()


@app.post("/upload/text")
async def upload_text(
    file: Annotated[UploadFile, File(description="文本文件")],
) -> dict[str, Any]:
    data = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(data),
    }


@app.post("/upload/bytes")
def upload_bytes(data: Annotated[bytes, File()]) -> dict[str, int]:
    return {"size": len(data)}
```

调用方式：

```python
client.post("/upload/text", files={"file": ("notes.txt", b"hello", "text/plain")})
```

完整版本（分块读、落盘观察、文件名穿越、content_type 撒谎）见 `examples/main.py`。

## 怎么跑

```powershell
cd "04-表单文件与编码\28-文件上传\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 上传文本文件 -> size=12，content_type=text/plain
[PASS] OpenAPI multipart/binary -> multipart/form-data + contentMediaType=application/octet-stream
[PASS] 缺文件 422 -> loc=['body', 'file']
[PASS] bytes 版本 -> size=10
[PASS] 空文件 -> size=0
[PASS] 分块读 + seek -> head=abcd，total=12
[PASS] 读两次为空 -> 首次 5 字节，再次 0 字节（需 seek(0)）
[PASS] size 属性 -> size=1024
[PASS] 小文件不落盘 -> 5 字节 → rolled_to_disk=False
[PASS] 大文件落盘 -> 1MB+1 字节 → rolled_to_disk=True
[PASS] 文件名穿越 -> given=../../etc/passwd → basename=passwd
[PASS] content_type 不可信 -> 声明 text/html，服务端原样收到（不可信）

结果：12/12 通过
```

## 核心 API 速查

| 写法 | 读法 | 适用 |
| --- | --- | --- |
| `Annotated[UploadFile, File()]` | `await f.read()` / `read(n)` | **默认选择**，大文件安全 |
| `Annotated[bytes, File()]` | 直接是 `bytes` | 确定很小的文件 |
| `Annotated[list[UploadFile], File()]` | 遍历 | 多文件（第 29 章）|

| `UploadFile` 成员 | 说明 |
| --- | --- |
| `filename` | 客户端提供的名字（不可信）|
| `content_type` | 客户端声明的类型（不可信）|
| `size` | 总字节数（Starlette 记录）|
| `file` | 底层 `SpooledTemporaryFile` |
| `await read(n)` | 读 n 字节，读完为空 |
| `await seek(0)` | 回到开头 |
| `await close()` | 关闭底层文件 |
| `headers` | 该 part 的头 |

| 事实 | 实测结果 |
| --- | --- |
| 空文件 | `size=0`，不报错 |
| 读完不 seek 再读 | `b""` |
| ≤1MB | `_rolled=False`（内存）|
| >1MB | `_rolled=True`（落盘）|
| OpenAPI 文件字段 | `type: string` + `contentMediaType: application/octet-stream`（**不是** `format: binary`）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用 `bytes` 接大文件 | 内存被打爆 | 用 `UploadFile` |
| 以为 `format: binary` 一定在 schema 里 | 实测是 `contentMediaType` | 断言两者都兼容 |
| 读完忘了 `seek(0)` 又读 | 拿到空内容 | 需要重读就 `seek` |
| 直接用 `file.filename` 存盘 | 路径穿越 | `Path(name).name` + UUID 重命名 |
| 用 `content_type` 判断安全性 | 客户端可撒谎 | 服务端嗅探/白名单扩展名校验 |
| 不限制大小 | 磁盘/内存耗尽 | 反代 `client_max_body_size` + 应用层校验 |
| 不关闭 `UploadFile` | 临时文件延迟释放 | 用完 `await close()` 或用依赖 yield |
| 以为 `File()` 会自动校验扩展名 | 不会 | 自己校验 |
| 同步端点里 `await file.read()` | 语法/运行错误 | `async def` 或 `file.file.read()` |
| 依赖 `_rolled` 做业务判断 | 实现细节会变 | 只用于演示 |

## 毕业自查

- [ ] 能说出 `UploadFile` 与 `bytes` 的内存差异
- [ ] 能说出 1MB 阈值与 `SpooledTemporaryFile`
- [ ] 能写出分块读取
- [ ] 能解释「读完再读为空」
- [ ] 能说出 `filename`/`content_type` 为什么不可信
- [ ] 能给出安全存盘的三步（清洗名、重命名、校验类型）
- [ ] 动手题一：上传后计算 SHA-256 并返回
- [ ] 动手题二：限制只能传 `.txt`（按扩展名 + 内容嗅探）

> 想看 multipart 报文结构、落盘与清理、大小限制的三种做法、安全校验清单、19 条坑，继续读 [`base.md`](./base.md)。