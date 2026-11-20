# 01 环境与第一个接口

## 一句话结论

FastAPI 的核心只有三件事：**建一个 `app` 实例 → 用装饰器把函数注册成路由 → 用类型标注描述入参和出参**。文档、校验、序列化都由这三件事自动推导出来。

学完这一章，你能：起一个服务、访问 `/docs`、说清「请求进来后框架做了哪 7 步」。

## 最小可运行案例

```python
from fastapi import FastAPI

app = FastAPI(title="第 01 章 · 第一个接口", version="0.1.0")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello FastAPI"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

完整带注释版本见 `examples/main.py`，自动验收见 `examples/verify.py`。

## 怎么跑

```powershell
# 1. 装依赖（在 FastAPI 根目录，全教程共用一套环境）
cd E:\ai-agent-study\FastAPI
uv sync

# 2. 启动（在章节目录执行，开热重载）
cd "00-起步\01-环境与第一个接口\examples"
uv run uvicorn main:app --reload

# 3. 浏览器打开
#    http://127.0.0.1:8000/docs      Swagger UI（可点「Try it out」直接发请求）
#    http://127.0.0.1:8000/redoc     ReDoc（只读的漂亮文档）
#    http://127.0.0.1:8000/openapi.json   机器可读的接口契约

# 4. 不想起服务？用验收脚本
uv run python verify.py
```

预期输出：

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

```text
[PASS] GET / 返回固定 JSON -> 200 {'message': 'Hello FastAPI'}
[PASS] GET /health 健康检查 -> 200 {'status': 'ok'}
[PASS] /openapi.json 结构正确 -> paths=['/', '/health']
[PASS] /docs 与 /redoc 可访问 -> /docs 200, /redoc 200
[PASS] 未知路径返回 404 -> 404 {'detail': 'Not Found'}
[PASS] 错误方法返回 405 -> 405 {'detail': 'Method Not Allowed'}

结果：6/6 通过
```

出错了按这个顺序排查：

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'fastapi'` | 没装依赖 / 用错解释器 | `uv sync`，确认 `uv run python -c "import fastapi"` 能过 |
| `Error loading ASGI app. Could not import module "main"` | 不在 `examples` 目录启动 | `cd` 到 `main.py` 所在目录再启动 |
| `[Errno 10048] address already in use` | 8000 端口被占 | 换端口：`uvicorn main:app --port 8001` |
| `/docs` 打开是空白 | 用了 `file://` 直开 HTML | 必须通过 `http://127.0.0.1:8000/docs` 访问 |

## 核心 API 速查

| API | 作用 | 必填 | 常用参数 |
| --- | --- | --- | --- |
| `FastAPI()` | 创建应用实例，所有组件挂在它上面 | — | `title`、`version`、`description`、`docs_url`、`redoc_url`、`openapi_url`、`lifespan`、`root_path`、`dependencies` |
| `@app.get(path)` | 注册 GET 路由 | `path` | `response_model`、`status_code`、`tags`、`summary`、`description`、`deprecated`、`include_in_schema`、`response_class`、`name` |
| `@app.post/put/patch/delete` | 注册其它方法 | `path` | 同上 |
| `app.include_router(router)` | 挂载子路由 | `router` | `prefix`、`tags`、`dependencies` |
| `uvicorn.run(app, host, port)` | 以代码方式启动 | `app` | `host`、`port`、`reload`、`log_level` |
| `TestClient(app)` | 不起服务直接测 | `app` | `base_url`、`headers` |

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `title` | `"FastAPI"` | 显示在 `/docs` 顶部，也会进 OpenAPI `info.title` |
| `version` | `"0.1.0"` | 显示在 `/docs` 顶部 |
| `docs_url` | `"/docs"` | 设为 `None` 即关闭 Swagger UI |
| `openapi_url` | `"/openapi.json"` | 设为 `None` 会同时关闭两个 UI |
| `root_path` | `""` | 部署在反向代理子路径下时用（第 54 章） |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 把 `app = FastAPI()` 写在函数里 | `Could not import module "main"` | 必须是**模块级**变量 |
| `def read_root()` 不写返回值标注 | 能跑，但 `/docs` 里没有响应结构 | 标注 `-> dict[str, str]` |
| 启动命令写 `uvicorn main:app` 但不在 `examples` 目录 | `Could not import module "main"` | 先 `cd` 到 `main.py` 所在目录 |
| `@app.get("items")` 少了前导斜杠 | 启动即报 `Path must start with /` | 写 `"/items"` |
| 用 `python main.py` 却想要热重载 | 改了代码不生效 | 用 `uvicorn main:app --reload` |
| 生产环境开 `--reload` | 多一个监控进程、内存翻倍 | 生产去掉 `--reload` |
| 以为 `/docs` 是给用户看的页面 | 对外暴露了完整接口清单 | 生产用 `docs_url=None` 或加鉴权 |
| 健康检查里查数据库 | 数据库抖一下，全部实例被重启 | 健康检查只返回进程自身状态 |

## 毕业自查

- [ ] 能不看资料写出「两个接口的最小服务」
- [ ] 能说出 `app` 为什么必须是模块级变量
- [ ] 能说出 `/docs`、`/redoc`、`/openapi.json` 三者的关系
- [ ] 能解释 404 与 405 分别代表什么
- [ ] 能说出返回值标注 `-> dict[str, str]` 带来的两个好处
- [ ] `verify.py` 跑出 6/6 通过
- [ ] 动手题一：加一个 `GET /version` 返回 `{"version": "0.1.0"}`，并在 `/docs` 里确认它出现
- [ ] 动手题二：把 `docs_url` 设为 `None`，重启后确认 `/docs` 变成 404，而 `/openapi.json` 仍在

> 想看机制、边界、40 条注意事项与依据索引，继续读 [`base.md`](./base.md)。
