# 68 子应用与静态资源

## 一句话结论

一个进程同时提供 API、静态资源、SPA 首页和子应用：`app.mount("/static", StaticFiles(...))`、`app.mount("/sub", sub_app)`、最后 `app.mount("/", StaticFiles(html=True))`。实测 CSS 返回 `text/css; charset=utf-8`、JS 返回 `text/javascript; charset=utf-8`、JSON 返回 `application/json`；`html=True` 让 `/` 返回 `index.html`，但 **`/some/route` 仍是 404**（它不做 SPA 深路径 fallback）；目录穿越 `/static/../main.py` 被拦成 404。子应用有独立的 `/sub/docs` 和 `/sub/openapi.json`，并且**不出现在主应用 schema 里**。最大的坑：**`mount` 不会触发子应用的 lifespan**，实测子应用 `state.marker` 是 `missing`、事件为空。

## 最小可运行案例

```text
examples/
├── main.py
├── subapp.py
└── static/
    ├── index.html
    ├── app.css
    ├── app.js
    └── data.json
```

`main.py`：

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from subapp import sub_app

STATIC = Path(__file__).parent / "static"

app = FastAPI()


@app.get("/api/items")
def items() -> dict[str, list[str]]:
    return {"items": ["a", "b", "c"]}


# 顺序：具体前缀在前，兜底 `/` 最后
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/sub", sub_app, name="sub")
app.mount("/", StaticFiles(directory=STATIC, html=True), name="spa")
```

`subapp.py`：

```python
from fastapi import FastAPI

sub_app = FastAPI(title="子应用")


@sub_app.get("/hello")
def hello() -> dict[str, str]:
    return {"who": "sub-app"}
```

## 怎么跑

```powershell
cd "11-应用结构\68-子应用与静态资源\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] API 优先 -> 200 / 3 条
[PASS] CSS MIME -> text/css; charset=utf-8
[PASS] JS MIME -> text/javascript; charset=utf-8
[PASS] JSON 静态 -> application/json / chapter=68
[PASS] 缺失 404 -> 404
[PASS] / 返回 index -> 200 / text/html
[PASS] 深路径 404 -> 深路径 404（需自写 fallback）
[PASS] 目录穿越 -> 404，未泄露源码
[PASS] 子应用端点 -> who=sub-app
[PASS] root_path -> sub "/sub"，main ""
[PASS] 子应用文档 -> /sub/docs + /sub/openapi.json
[PASS] 主应用文档 -> 200
[PASS] 子应用不进主 schema -> 主 schema 无 /sub/hello
[PASS] 静态不进 schema -> 无 /static/* 条目
[PASS] 子应用 lifespan 不级联 -> 子应用 marker=missing，事件为空
[PASS] 直接跑子应用 -> sub:startup → sub:shutdown

结果：16/16 通过
```

## 核心 API 速查

| 写法 | 作用 |
| --- | --- |
| `app.mount("/static", StaticFiles(directory=...))` | 挂一个目录 |
| `StaticFiles(html=True)` | 目录里有 `index.html` 时自动返回 |
| `app.mount("/sub", sub_app)` | 挂一个独立 FastAPI 实例 |
| `name="static"` | 供 `url_path_for` 使用 |
| `check_dir=True`（默认）| 启动时校验目录存在 |

| 实测 | 值 |
| --- | --- |
| `app.css` | `text/css; charset=utf-8` |
| `app.js` | `text/javascript; charset=utf-8` |
| `data.json` | `application/json` |
| `/` | 200 `text/html`（index.html）|
| `/some/route` | **404**（不兜底）|
| `/static/../main.py` | 404 |
| `/sub/hello` | 200，`root_path="/sub"` |
| `/sub/docs` | 200 |
| 子应用 lifespan | **不触发** |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 先挂 `/` 再挂 `/api` | API 全被静态 404 | 具体在前，`/` 最后 |
| 以为 `html=True` 能兜 SPA 深路径 | 刷新页面 404 | 自写 404 兜底返回 index |
| 期待子应用 lifespan 自动跑 | `state` 空、预热没做 | 主应用 lifespan 里手动跑 |
| 静态目录不存在 | 启动即 `RuntimeError` | `check_dir=False` 或保证存在 |
| 把源码目录挂成静态 | 泄露 `.py`/`.env` | 只挂 `dist/` 等构建产物 |
| 用 `../` 访问上级 | 依赖默认拦截 | 保持默认，别自定义不安全实现 |
| 静态挂载进 OpenAPI | 文档被污染 | 默认就不会进 |
| 子应用也用主应用前缀 | 路径翻倍 | 子应用内部写相对路径 |
| 生产用 `--reload` | 性能差 | 关闭 |
| 让静态服务处理大文件 | 内存/带宽 | 交给 Nginx/CDN |
| 不设缓存头 | 每次全量下载 | `Cache-Control` 中间件 |
| 用 mount 做权限控制 | 静态资源绕过依赖 | 自定义 `StaticFiles` 子类 |
| 子应用 docs 与主 docs 路径冲突 | 覆盖 | 给子应用独立前缀 |
| SPA 路由与 API 路由同构 | 误判 | API 用 `/api` 前缀隔离 |

## 毕业自查

- [ ] 能挂静态目录并验证 MIME
- [ ] 能解释 `html=True` 的边界
- [ ] 能挂子应用并访问它的 docs
- [ ] 能说清 `root_path` 在子应用里的值
- [ ] 知道子应用 lifespan 不会自动跑
- [ ] 动手题一：给 SPA 加深路径 fallback
- [ ] 动手题二：给静态资源加 `Cache-Control: max-age=3600`

> 想看 `Mount` 的 ASGI 路由原理、`StaticFiles` 的路径安全、子应用 `root_path` 传播、CDN 与缓存、18 条坑，继续读 [`base.md`](./base.md)。