"""API 文档的三个入口。

| 地址 | 引擎 | 适合 |
|---|---|---|
| `/docs` | Swagger UI | **发真实请求调试**，能填参数、看响应、看耗时 |
| `/scalar` | Scalar | **颜值最高**，三栏布局 + 深色主题，接近 Knife4j 的观感 |
| `/redoc` | ReDoc | **中文界面**，左侧导航，适合把文档发给别人看 |

**关于 Knife4j**：它是 Java 生态的（依赖 Springfox / Springdoc 的注解扫描），
Python 无法直接使用。但三者读的是**同一份 OpenAPI 文档**，信息完全一致，
只是渲染风格不同。

**关于静态资源**：这三个引擎的 JS/CSS 默认都从 `cdn.jsdelivr.net` 加载，
而该域名在部分网络环境下不可达，表现为「页面一片空白」。
所以本项目把资源下载到了 `app/static/docs/`，**默认离线加载**；
文件缺失时才回退 CDN（见 `_asset`）。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# app/static —— 相对本文件定位，不受启动目录影响
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_DOCS_DIR = _STATIC_DIR / "docs"
_STATIC_URL = "/static/docs"

# 本地文件缺失时的兜底地址（联网环境下仍可用）
_CDN = {
    "scalar": "https://cdn.jsdelivr.net/npm/@scalar/api-reference",
    "swagger_js": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    "swagger_css": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    "redoc": "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
}


def _asset(filename: str, cdn: str) -> str:
    """优先用本地文件，缺失时才回退 CDN。

    这样内网/断网环境下文档照常打开，而有网的部署环境也不会因为
    忘了拷贝 static 目录就彻底失效。
    """
    return f"{_STATIC_URL}/{filename}" if (_DOCS_DIR / filename).exists() else cdn


_SCALAR_PAGE = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>__TITLE__ · API 文档</title>
    <style>
      body { margin: 0; }
      #scalar-error {
        display: none;
        font-family: system-ui, sans-serif;
        padding: 40px;
        line-height: 1.8;
      }
    </style>
  </head>
  <body>
    <noscript>
      <p style="font-family: system-ui; padding: 40px">
        这个页面需要 JavaScript。请改用 <a href="/docs">Swagger UI</a> 或 <a href="/redoc">ReDoc</a>。
      </p>
    </noscript>

    <!--
      只在 <script onerror> 时显示 —— 这是「资源真的没取到」的唯一可靠信号。

      不要用「探测 DOM 里有没有 scalar-api-reference」来判断：
      新版 Scalar 根本不注册这个自定义元素（只挂 window.Scalar），
      那种检测必然失败，会把已经渲染好的页面整个覆盖成错误提示。
    -->
    <div id="scalar-error">
      <h2>Scalar 资源加载失败</h2>
      <p>浏览器没能取到 <code>static/docs/scalar-standalone.js</code>。</p>
      <p>可以继续使用：<a href="/docs">Swagger UI</a> 或 <a href="/redoc">ReDoc</a></p>
    </div>

    <!-- OpenAPI 地址由后端注入，改端口/前缀时不用动这里 -->
    <script id="api-reference" data-url="__OPENAPI__"></script>

    <script>
      document.getElementById('api-reference').dataset.configuration = JSON.stringify({
        theme: 'purple',
        layout: 'modern',
        hideDarkModeToggle: false,
        hideDownloadButton: false,
        searchHotKey: 'k',
        defaultOpenAllTags: false,
      })
    </script>

    <script src="__CDN__"
            onerror="document.getElementById('scalar-error').style.display='block'"></script>
  </body>
</html>
"""

_REDOC_PAGE = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>__TITLE__ · API 文档</title>
    <style>
      body { margin: 0; padding: 0; }
      #redoc-error {
        display: none;
        font-family: system-ui, sans-serif;
        padding: 40px;
        line-height: 1.8;
      }
    </style>
  </head>
  <body>
    <div id="redoc-error">
      <h2>ReDoc 资源加载失败</h2>
      <p>浏览器没能取到 <code>static/docs/redoc.standalone.js</code>。</p>
      <p>可以继续使用：<a href="/docs">Swagger UI</a> 或 <a href="/scalar">Scalar</a></p>
    </div>

    <!--
      用 div + Redoc.init() 而不是 <redoc spec-url="...">：
      后者依赖 Web Component 自动注册，而 ReDoc 2.x 的 UMD 包并不注册该元素，
      3.x 更是改成了纯 ESM（带 export，普通 <script> 会直接语法报错）。
      Redoc.init 是两代都兼容的稳定 API。
    -->
    <div id="redoc-container"></div>

    <script src="__CDN__"
            onerror="document.getElementById('redoc-error').style.display='block'"></script>

    <script>
      (function () {
        var host = document.getElementById('redoc-container')
        var fail = document.getElementById('redoc-error')

        if (!window.Redoc || typeof window.Redoc.init !== 'function') {
          fail.style.display = 'block'
          return
        }

        // <html lang="zh-CN"> 会让 ReDoc 输出中文界面
        window.Redoc.init(
          '__OPENAPI__',
          {
            expandResponses: '200',
            requiredPropsFirst: true,
            hideDownloadButton: false,
            scrollYOffset: 0,
          },
          host,
          function (err) {
            if (err) {
              fail.style.display = 'block'
            }
          }
        )
      })()
    </script>
  </body>
</html>
"""


def setup_docs(app: FastAPI, *, title: str, openapi_url: str) -> None:
    """挂载文档页与它们的静态资源。在 create_app 里调用一次。"""
    # 静态资源：/static/docs/scalar-standalone.js 之类
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    scalar_src = _asset("scalar-standalone.js", _CDN["scalar"])
    redoc_src = _asset("redoc.standalone.js", _CDN["redoc"])

    scalar_html = (
        _SCALAR_PAGE.replace("__TITLE__", title)
        .replace("__OPENAPI__", openapi_url)
        .replace("__CDN__", scalar_src)
    )
    redoc_html = (
        _REDOC_PAGE.replace("__TITLE__", title)
        .replace("__OPENAPI__", openapi_url)
        .replace("__CDN__", redoc_src)
    )

    # include_in_schema=False：文档页不出现在接口列表里

    @app.get("/docs", include_in_schema=False, tags=["docs"])
    async def swagger_docs() -> HTMLResponse:
        """手动生成，为了把 JS/CSS 指到本地文件。

        FastAPI 的 docs_url 只接受「用不用」，不能换资源地址，
        所以关掉它（docs_url=None）之后在这里重建一份。
        """
        return get_swagger_ui_html(
            openapi_url=openapi_url,
            title=f"{title} · Swagger UI",
            swagger_js_url=_asset("swagger-ui-bundle.js", _CDN["swagger_js"]),
            swagger_css_url=_asset("swagger-ui.css", _CDN["swagger_css"]),
            # 复用 create_app 里配好的行为参数（展开方式、搜索框、耗时显示等）
            swagger_ui_parameters=app.swagger_ui_parameters,
        )

    @app.get("/scalar", include_in_schema=False, tags=["docs"])
    async def scalar_docs() -> HTMLResponse:
        return HTMLResponse(scalar_html)

    @app.get("/redoc", include_in_schema=False, tags=["docs"])
    async def redoc_docs() -> HTMLResponse:
        return HTMLResponse(redoc_html)
