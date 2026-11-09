# agent-lab 本地开发说明

前后端分离的两个工程：

```
code/
├── agent-lab/        后端 · FastAPI + SQLite（Python 3.12 / uv）
└── agent-lab-web/    前端 · Vue3 + Vite + TS（Node 20+ / npm）
```

| 服务 | 地址 |
|---|---|
| 后端 API | http://127.0.0.1:8001/api/v1 |
| 接口文档 · Swagger UI（调试用） | http://127.0.0.1:8001/docs |
| 接口文档 · Scalar（颜值最高） | http://127.0.0.1:8001/scalar |
| 接口文档 · ReDoc（中文阅读） | http://127.0.0.1:8001/redoc |
| OpenAPI 原始描述 | http://127.0.0.1:8001/api/v1/openapi.json |
| 前端页面 | http://127.0.0.1:5173 |

---

## 一、一次性安装依赖

### 后端

```powershell
cd E:\ai-agent-study\code\agent-lab
uv sync
```

> `uv sync` 会按 `pyproject.toml` 创建 `.venv` 并装好全部依赖。
> 如果还没装 uv：`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### 前端

```powershell
cd E:\ai-agent-study\code\agent-lab-web
npm install
```

---

## 二、启动（需要两个终端，都要保持开着）

### 终端 1 · 后端

```powershell
cd E:\ai-agent-study\code\agent-lab
uv run python run.py
```

启动成功的标志（最后一行必须有）：

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001
```

### 终端 2 · 前端

```powershell
cd E:\ai-agent-study\code\agent-lab-web
npm run dev
```

启动成功的标志：

```
VITE v8.x  ready in 400 ms
➜  Local:   http://127.0.0.1:5173/
```

然后浏览器打开 **http://127.0.0.1:5173**

---

## 三、一键启动（可选）

```powershell
cd E:\ai-agent-study\code
.\dev.ps1
```

会同时弹出两个 PowerShell 窗口分别运行前后端。

> 首次运行若报错「禁止运行脚本」，执行一次：
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

---

## 四、验证是否通了

| 检查 | 方式 | 期望 |
|---|---|---|
| 后端活着 | 浏览器开 `http://127.0.0.1:8001/api/v1/health` | `{"status":"ok","version":"0.1.0"}` |
| 文档 · Swagger | 浏览器开 `http://127.0.0.1:8001/docs` | 紫色顶栏，接口按 tag 分组 |
| 文档 · Scalar | 浏览器开 `http://127.0.0.1:8001/scalar` | 三栏布局，左侧导航 |
| 文档 · ReDoc | 浏览器开 `http://127.0.0.1:8001/redoc` | 中文界面，左侧目录 |
| OpenAPI JSON | 浏览器开 `http://127.0.0.1:8001/api/v1/openapi.json` | 一段 JSON，开头是 `"openapi": "3.1.0"` |
| 前端活着 | 浏览器开 `http://127.0.0.1:5173` | 看到待办 + 流式两个面板 |
| 代理通了 | 前端页面能加载待办列表 | 列表为空不报错即可 |

### 三个文档入口的区别

三者读的是**同一份 OpenAPI 文档**（`/api/v1/openapi.json`），只是渲染风格不同：

| 入口 | 引擎 | 适合 |
|---|---|---|
| `/docs` | Swagger UI | **调接口**：能填参数、发真实请求、看响应和耗时 |
| `/scalar` | Scalar | **演示 / 截图**：三栏布局 + 深色主题，最接近 Knife4j 的观感 |
| `/redoc` | ReDoc | **阅读 / 分享**：中文界面、纯展示，适合发给别人看 |

> 文档引擎的 JS/CSS 已下载到 `agent-lab/src/agent_lab/app/static/docs/`，
> **不走 CDN，断网也能打开**。只有文件缺失时才回退 jsdelivr
> （该域名在部分网络环境下不可达，表现为页面空白）。

---

## 五、常用命令

### 后端

```powershell
uv run python run.py                  # 启动（含热重载）
uv run uvicorn agent_lab.app.main:app --port 8001 --reload   # 等价写法
uv add <包名>                          # 加依赖（会同时写进 pyproject.toml）
uv run python -c "import agent_lab"   # 快速验证包能导入
```

### 前端

```powershell
npm run dev       # 开发服务器（热更新）
npm run build     # 生产构建（含 vue-tsc 类型检查）
npm run preview   # 预览构建产物
npx vue-tsc -b --force   # 强制全量类型检查
```

---

## 六、停止服务

**按 `Ctrl + C`**，不要直接关窗口。

> 关窗口在 Windows 上不一定会结束子进程，会出现端口被占用、
> 下次启动报 `WinError 10048` / `10013` 的情况。

---

## 七、常见问题

### 1. `ImportError: attempted relative import with no known parent package`

**原因**：直接跑了 `python src\agent_lab\app\main.py`。

**解决**：必须用入口脚本或 uvicorn：

```powershell
uv run python run.py                    # ✅
uv run python -m agent_lab.app.main     # ✅
python src\agent_lab\app\main.py        # ❌
```

### 2. 端口被占用

```powershell
netstat -ano | findstr ":8001"
taskkill /PID <上一条查到的PID> /T /F
```

### 3. 端口在监听，但请求超时

通常是**同一命令起了两份**（僵尸进程）。清理后重启：

```powershell
netstat -ano | findstr ":8001"
taskkill /PID <PID1> /T /F
taskkill /PID <PID2> /T /F
```

### 4. 前端报 `Cannot find module './App.vue'` 或 `startsWith 不存在`

**原因**：编辑器用了内置的旧版 TypeScript。

**解决**：

```
Ctrl + Shift + P  →  TypeScript: Select TypeScript Version  →  Use Workspace Version
Ctrl + Shift + P  →  TypeScript: Restart TS Server
```

命令行的判定标准（这个过了就说明代码没问题）：

```powershell
cd E:\ai-agent-study\code\agent-lab-web
npx vue-tsc -b --force    # 无输出 = 通过
```

### 5. 前端页面打开一片白

按 `F12` 看 Console：

| 报错 | 原因 |
|---|---|
| `Failed to fetch` / `ECONNREFUSED` | 后端没启动，或没起在 8001 |
| `404` 且路径是 `/api/v1/...` | 后端路由没注册 |
| 静态资源 404 | 检查是否误访问了 `dist/index.html` 的本地文件路径 |

### 6. 改了后端代码没生效

`run.py` 已开启 `reload=True`，正常情况下会自己重启。

如果没反应，说明 reload 进程挂了（见问题 3），重启一次即可。

### 7. 文档页面打不开 / 提示「资源加载失败」

先确认后端真的在跑：

```powershell
curl http://127.0.0.1:8001/api/v1/health
```

再确认静态资源在不在：

```powershell
dir E:\ai-agent-study\code\agent-lab\src\agent_lab\app\static\docs
```

应有 4 个文件：`scalar-standalone.js`、`swagger-ui-bundle.js`、`swagger-ui.css`、`redoc.standalone.js`。

| 现象 | 原因 / 解决 |
|---|---|
| 三个文档全白 | 后端进程是改代码前启动的，`app.mount` 没生效 → 重启 |
| 只有 `/scalar` 白 | 本地文件缺失 → 用上面的 `dir` 检查 |
| 页面显示「资源加载失败」 | 该 JS 请求 404，按 F12 在 Network 里看具体路径 |
| 强刷后才正常 | 浏览器缓存了旧 HTML，用 `Ctrl + Shift + R` |

---

## 八、目录速查

### 后端 `agent-lab/src/agent_lab/app/`

```
main.py              应用装配（lifespan / CORS / 路由 / 异常 / 文档）
core/config.py       全局配置（含 TIME_OUTPUT_UTC / TIME_FORMAT）
core/db.py           SQLite 连接与建表
core/errors.py       统一异常与错误响应格式
core/time.py         时间取用与序列化（全项目唯一格式来源）
core/docs.py         三个文档入口 + 静态资源挂载
models/todo.py       Pydantic 数据契约
services/todo.py     业务逻辑（纯 SQL，不依赖 FastAPI）
api/v1/router.py     v1 路由汇总
api/v1/health.py     健康检查
api/v1/todos.py      待办 CRUD
api/v1/demo.py       SSE 流式演示
static/docs/         文档引擎的离线资源（Scalar / Swagger / ReDoc）
```

### 前端 `agent-lab-web/src/`

```
api/http.ts          fetch 封装 + 统一错误
api/todos.ts         待办接口
api/stream.ts        SSE 流式解析
components/          TodoPanel.vue / StreamPanel.vue
App.vue              两栏布局
```

数据文件：`agent-lab/data/app.db`（SQLite，首次启动自动创建）
