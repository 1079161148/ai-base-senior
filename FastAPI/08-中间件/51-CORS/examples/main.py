"""第 51 章 · CORS（跨域资源共享）。

核心：CORS 是**浏览器**的同源策略保护，服务端只是「声明允许谁」。
      `CORSMiddleware` 做三件事：给真实响应加 `Access-Control-Allow-Origin`、
      应答预检 `OPTIONS`、把 `Vary: Origin` 写对（缓存正确性）。
      它是个中间件，所以 **404 也会带 CORS 头**（第 50 章）。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

ALLOWED_ORIGIN = "http://localhost:3000"

app = FastAPI(title="第 51 章 · CORS", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    # 【注意】只写协议+主机+端口，**不能带路径**、不能带尾斜杠
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Token", "Content-Type"],
    # 【作用】让浏览器 JS 能读到这些响应头（默认只暴露少数几个）
    expose_headers=["X-Total"],
    # 【作用】预检结果缓存秒数，减少 OPTIONS 请求
    max_age=600,
)


@app.get("/data", tags=["CORS"], summary="被跨域调用的接口")
def read_data() -> JSONResponse:
    return JSONResponse(
        {"items": [1, 2, 3]},
        headers={"X-Total": "3"},
    )


@app.post("/data", tags=["CORS"], summary="带自定义头的 POST")
def create_data(payload: dict[str, Any]) -> dict[str, Any]:
    return {"created": payload}


# ============================================================
# 对照：`*` + credentials 的组合
# ============================================================
star_app = FastAPI(title="CORS 星号对照")

star_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@star_app.get("/data")
def star_data() -> dict[str, str]:
    return {"mode": "star"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)