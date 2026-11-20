# 68 子应用与静态资源 · 完整版（base.md）

> `README.md` 给你能跑的「API + 静态 + SPA + 子应用」；本文件把「`mount` 到底做了什么、`root_path` 怎么传、子应用为什么不跑 lifespan、目录穿越怎么防」拆开。学完这章，你能判断一个「刷新页面 404、静态资源被 API 抢走、子应用启动日志没打」的问题出在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 65 章（应用拆分）、第 67 章（lifespan） |
| 覆盖范围 | `StaticFiles`、`app.mount`、子应用、`root_path`、路由顺序 |
| 明确不覆盖 | CDN 配置、Nginx 静态托管、前端构建工具链 |
| 学完验收 | 能跑通 `verify.py` 16/16、能解释子应用 lifespan 的坑 |

## 0. 怎么用这份文件

**依据约定**：`` `[Mn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → mount 是「前缀交给另一个 ASGI 应用」
2 机制（第 2 节）    → 路径重写与 root_path
3 API（第 3 节）     → StaticFiles 参数
4 边界（第 4 节）    → 顺序、lifespan、穿越、缓存
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 部署形状
```

## 1. 概念：`mount` 是前缀委托

```text
GET /static/app.css
  → 主应用匹配到 Mount("/static", StaticFiles(...))
  → 去掉前缀 → "app.css"
  → 交给 StaticFiles 处理
  → 200
```

| 项 | 普通路由 | `mount` |
| --- | --- | --- |
| 匹配粒度 | 精确路径 | 整个前缀 |
| 处理者 | 端点函数 | 任意 ASGI app |
| 进 OpenAPI | 是 | 否 |

## 2. 机制

### 2.1 路径与 `root_path`（实测）

| 应用 | `scope["path"]` | `scope["root_path"]` |
| --- | --- | --- |
| 主应用 `/api/whoami` | `/api/whoami` | `""` |
| 子应用 `/sub/hello` | `/hello` | **`/sub`** |

**结论**：子应用内部只看到相对路径，挂载前缀在 `root_path` 里。所以子应用里生成的 URL 要带 `root_path` 才正确（`url_for` 会处理）。

### 2.2 子应用的文档（实测）

```text
/sub/docs          200
/sub/openapi.json  200（paths 里是 /hello，不带 /sub）
主 /openapi.json   不含 /sub/hello
```

### 2.3 子应用 lifespan 不级联（实测坑）

```text
with TestClient(main.app):
    主应用 events = ["app:startup"]
    子应用 events = []
    子应用 state.marker = missing
```

| 做法 | 子应用 lifespan |
| --- | --- |
| `app.mount("/sub", sub_app)` | **不执行** |
| `TestClient(sub_app)` | 执行 |

**对策**：需要预热的资源在主应用 lifespan 里显式初始化并塞给子应用，或者子应用改成懒加载。

## 3. API 逐个拆解

| 参数 | 作用 | 默认 |
| --- | --- | --- |
| `directory` | 目录路径（str 或 Path）| 必填 |
| `packages` | 从包内找目录 | 无 |
| `html=True` | 目录请求返回 `index.html` | `False` |
| `check_dir=True` | 启动时校验目录存在 | `True` |
| `follow_symlink` | 跟随符号链接 | `False` |

### 3.1 MIME（实测）

| 文件 | `Content-Type` |
| --- | --- |
| `.css` | `text/css; charset=utf-8` |
| `.js` | `text/javascript; charset=utf-8` |
| `.json` | `application/json` |
| `.html` | `text/html; charset=utf-8` |

MIME 由 `mimetypes` 猜，部署环境缺映射时可能变成 `text/plain`。

### 3.2 `html=True` 的边界（实测）

| 请求 | 结果 |
| --- | --- |
| `/` | `index.html` |
| `/some/route` | **404** |

它只处理「目录索引」，不做前端路由回退。SPA 需要自己兜底：

```python
@app.exception_handler(404)
async def spa_fallback(request, exc):
    if request.url.path.startswith("/api"):
        raise exc
    return FileResponse(STATIC / "index.html")
```

实测未覆盖该兜底写法，标注为**推导**。

### 3.3 `name=` 的用途

```python
app.mount("/static", StaticFiles(directory=...), name="static")
request.url_for("static", path="app.css")
```

`name` 不写时无法用 `url_for` 反查。

## 4. 边界条件

### 4.1 挂载顺序（实测）

```python
app.mount("/static", ...)   # 先
app.mount("/sub", ...)      # 中
app.mount("/", ...)         # 最后
```

| 顺序 | 结果 |
| --- | --- |
| 具体在前 | `/api/items` 200 |
| `/` 在前 | `/api/items` 被静态 404 |

`Mount("/")` 会匹配一切，所以必须最后。

### 4.2 目录穿越（实测）

```text
GET /static/../main.py → 404
```

Starlette 的 `StaticFiles` 会做路径规范化并拒绝越界。**不要**自己写 `open(request.path)`。

### 4.3 静态资源与鉴权

`mount` 的请求**不经过**依赖注入，所以 router 级 `dependencies` 管不到静态文件。

| 需求 | 做法 |
| --- | --- |
| 私有静态资源 | 自定义 `StaticFiles` 子类，在 `__call__` 里校验 |
| 公开资源 | 默认即可 |

### 4.4 缓存

| 头 | 效果 |
| --- | --- |
| 无 | 每次全量 |
| `Cache-Control: max-age=3600` | 浏览器缓存 1 小时 |
| 带 hash 文件名 + `immutable` | 永久缓存 |

静态资源默认不带 `Cache-Control`，生产建议加中间件。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `/` 先挂 | API 全 404 | 具体前缀在前 | 实测 |
| 以为 `html=True` 兜 SPA | 深路径 404 | 自写 404 回退 | 实测 |
| 期待子应用 lifespan | state 空 | 主应用里初始化 | 实测 |
| 静态目录不存在 | 启动崩 | `check_dir=False` | 实测 |
| 挂源码目录 | 泄露源码/密钥 | 只挂构建产物 | 实测 |
| 自写路径拼接 | 穿越漏洞 | 用 `StaticFiles` | 实测 |
| 想用依赖保护静态 | 不生效 | 子类化 | 实测 |
| 静态进 OpenAPI | 文档污染 | 默认不会 | 实测 |
| 子应用重复加前缀 | 路径翻倍 | 内部写相对 | 实测 |
| 生产 `--reload` | 性能差 | 关闭 | `[M3]` |
| 用 FastAPI 传大文件 | 占进程 | Nginx/CDN | `[M3]` |
| 不设缓存头 | 重复下载 | 加中间件 | `[M2]` |
| 子应用 docs 冲突 | 覆盖 | 独立前缀 | 实测 |
| API 与 SPA 路径同构 | 误判 | `/api` 隔离 | 实测 |
| `directory` 用相对路径 | 依赖 cwd | 用 `Path(__file__)` | 实测 |
| 挂载后改目录内容 | 需重启才能识别新文件 | 重建 `StaticFiles` | `[M2]` |
| 符号链接 | 默认不跟随 | 显式 `follow_symlink` | `[M2]` |
| 用 `mount` 做多版本 API | 文档不合并 | 用 `APIRouter` | 实测 |
| 子应用与主应用用相同 `openapi_url` | 文档路径互相覆盖 | 各自独立前缀 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 典型形状

```text
/               SPA（StaticFiles html=True）
/static/*       构建产物（js/css/img）
/api/*          JSON API
/sub/*          独立子应用（如管理后台）
```

### 6.2 目录

```python
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
```

绝对路径，不依赖启动目录。

### 6.3 检查清单

| 检查项 | 原因 |
| --- | --- |
| `/` 最后挂 | 不吞 API |
| 只挂构建产物 | 防泄露 |
| `Path(__file__)` | 路径稳定 |
| 缓存头 | 性能 |
| SPA 兜底 | 刷新不 404 |
| 子应用预热在主应用 | lifespan 不级联 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[M1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/sub-applications/ | 子应用 |
| `[M2]` | 文档 | https://www.starlette.io/staticfiles/ | `StaticFiles` |
| `[M3]` | 文档 | https://www.uvicorn.org/deployment/ | 部署 |

> **核对状态**：`[M1]`–`[M3]` 为官方文档链接，**本次未逐页直连复核**；API 优先、CSS/JS/JSON MIME、缺失 404、`/` 返回 index、深路径 404、目录穿越 404、子应用端点、`root_path`、子应用 docs、主文档、子应用不进主 schema、静态不进 schema、子应用 lifespan 不级联、直接跑子应用为生命周期均为本机实测，`examples/verify.py` 复现 16/16 通过。SPA 404 回退实现、缓存头、私有静态鉴权、Nginx 托管**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] `mount` 做了什么（前缀委托 + 路径重写）
- [ ] `root_path` 在子应用里的值
- [ ] 为什么 `/` 必须最后挂
- [ ] `html=True` 的边界
- [ ] 为什么子应用 lifespan 不跑

**能写出（代码层）**：

- [ ] 静态挂载
- [ ] 子应用挂载
- [ ] 子应用独立 docs
- [ ] 目录穿越验证
- [ ] `Path(__file__)` 定位

**能判断（避坑层）**：

- [ ] 看到刷新 404 → 想到缺 SPA 兜底
- [ ] 看到 API 404 → 想到 `/` 先挂
- [ ] 看到子应用 state 空 → 想到 lifespan
- [ ] 看到静态泄露源码 → 想到挂错目录
- [ ] 看到依赖保护静态无效 → 想到子类化

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 16/16
- [ ] 浏览器打开 `/` 看到页面，`/static/app.css` 生效
- [ ] 浏览器打开 `/sub/docs` 看到子应用文档

## 9. 下一章衔接

第 69 章 `OpenAPI 定制`：`title/description/servers`、`openapi_tags`、自定义 `openapi()`、隐藏内部端点、给前端交付契约。

本章留下的伏笔：

1. 子应用不进主 schema（68）→ 69 决定是否聚合。
2. 静态不进文档（68）→ 69 用 `openapi_tags` 整理分组。
3. `root_path`（68）→ 69 的 `servers` 要写对外地址。