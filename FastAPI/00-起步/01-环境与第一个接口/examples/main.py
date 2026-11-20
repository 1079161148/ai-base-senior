"""第 01 章 · 最小可运行的 FastAPI 服务。

本章目标：把服务跑起来，看清 FastAPI 到底替你做了什么。

三种启动方式（任选其一）：
  1. 在本目录执行：python main.py
  2. 在本目录执行：uvicorn main:app --reload
  3. 自动验收（不占端口）：python verify.py
"""

from fastapi import FastAPI

# 【作用】创建应用实例。它是所有路由、中间件、异常处理器的注册中心。
# 【注意】必须赋值给「模块级变量」：uvicorn 用字符串 "main:app" 查找它，
#        写在函数内部会报 "Could not import module 'main'"。
# 【为什么】模块级单例保证一个进程只有一个 app 实例；热重载时模块重载，
#        也不会出现「同一个路由注册两次」。
app = FastAPI(
    # 【作用】以下三项都会直接展示在 /docs 页面顶部
    title="第 01 章 · 第一个接口",
    description="最小可运行示例：两个 GET 接口 + 自动生成的交互文档",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    """根路径：返回一句问候。

    【作用】`@app.get("/")` 把下面这个函数注册为「GET / 」的处理器。
    【注意】返回值标注成 `dict[str, str]`，FastAPI 会：
           1) 按标注生成响应 schema 写进 OpenAPI；
           2) 自动 JSON 序列化，并设置 Content-Type: application/json。
    【为什么】不标注也能跑，但 /docs 里就看不到响应结构，前端只能靠猜。
    """
    return {"message": "Hello FastAPI"}


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查：给负载均衡、K8s 探针、监控系统用。

    【注意】健康检查必须极轻：不查数据库、不调外部服务、不加锁。
           检查「下游依赖是否可用」是就绪探针（readiness）的职责，
           不是存活探针（liveness）的职责——混在一起会导致依赖抖动时整批实例被重启。
    """
    return {"status": "ok"}


if __name__ == "__main__":
    # 【作用】支持 `python main.py` 直接启动，省去记 uvicorn 命令。
    # 【注意】这里传入的是 app 对象，所以不能开 reload；
    #        需要热重载就用命令行：uvicorn main:app --reload
    # 【注意】host 写 127.0.0.1 只有本机能访问；容器/局域网需改 "0.0.0.0"。
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
