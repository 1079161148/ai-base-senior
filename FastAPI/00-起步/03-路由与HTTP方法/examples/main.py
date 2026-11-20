"""第 03 章 · 路由与 HTTP 方法。

本章只做一件事：把「路径 + 方法 → 函数」的映射关系彻底讲清。
故意不引入请求体（Pydantic 模型），用查询参数代替，把注意力留给路由本身。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from __future__ import annotations

from fastapi import FastAPI, Response, status

app = FastAPI(title="第 03 章 · 路由与 HTTP 方法", version="0.1.0")

# 【作用】用一个进程内字典当数据库，避免引入真实数据库（第 55 章才讲）
# 【注意】模块级可变状态在 `--workers N` 下每进程一份，这里仅用于单进程演示
DB: dict[int, str] = {1: "苹果", 2: "香蕉"}


# ============================================================
# 关键点 1：精确路径必须注册在通配路径之前
# ============================================================
# 【为什么】FastAPI 的路由表是**有序列表**，按注册顺序逐个用正则匹配，
#          第一个匹配成功即返回。`/items/{item_id}` 能匹配 `/items/latest`，
#          所以它一旦排在前面，`latest` 就永远轮不到。
@app.get("/items/latest", tags=["商品"], summary="最新商品")
def get_latest() -> dict[str, str]:
    """返回最新商品。路径里有 `latest` 这种「看起来像 ID」的固定段时必须先注册。"""
    return {"latest": "苹果"}


@app.get("/items", tags=["商品"], summary="商品列表")
def list_items() -> list[dict[str, object]]:
    """返回全部商品。注意路径是 `/items`，与 `/items/{item_id}` 不冲突。"""
    return [{"id": k, "name": v} for k, v in DB.items()]


@app.get("/items/{item_id}", tags=["商品"], summary="商品详情")
def get_item(item_id: int) -> dict[str, object]:
    """按 ID 查商品。

    【作用】`{item_id}` 是路径参数，函数参数同名即可自动注入。
    【注意】标注 `int` 后，`/items/abc` 会返回 **422**（不是 404）：
           路径匹配成功，但类型转换失败。
    """
    # 【注意】真实项目这里应抛 HTTPException(404)，此处演示「找不到返回 null 字段」
    return {"id": item_id, "name": DB.get(item_id)}


# ============================================================
# 关键点 2：四种方法 + 正确的状态码
# ============================================================
# 【作用】201 Created：创建成功，通常配合 Location 头返回新资源地址
@app.post("/items", tags=["商品"], status_code=status.HTTP_201_CREATED, summary="创建商品")
def create_item(name: str) -> dict[str, object]:
    """创建商品。`name` 是查询参数（`POST /items?name=橘子`）。

    【注意】本章为了聚焦路由，用查询参数接收数据；
           真实创建的入参应放请求体（第 13 章）。
    """
    new_id = max(DB) + 1 if DB else 1
    DB[new_id] = name
    return {"id": new_id, "name": name}


@app.put("/items/{item_id}", tags=["商品"], summary="全量替换")
def replace_item(item_id: int, name: str) -> dict[str, object]:
    """PUT 语义：用请求内容**完整替换**目标资源。

    【注意】PUT 要求幂等：同样的请求发 N 次，结果一致。
    """
    DB[item_id] = name
    return {"id": item_id, "name": name}


@app.patch("/items/{item_id}", tags=["商品"], summary="部分更新")
def patch_item(item_id: int, name: str | None = None) -> dict[str, object]:
    """PATCH 语义：只改传入的字段，未传的保持原值。

    【注意】PATCH 不要求幂等，但在实践里也应尽量做成幂等。
    """
    if name is not None:
        DB[item_id] = name
    return {"id": item_id, "name": DB.get(item_id)}


# 【作用】204 No Content：删除成功且无内容返回
# 【注意】204 按规范**不能有响应体**，所以函数必须返回 Response 对象，
#        不能 `return {"ok": True}`——那会产生响应体，部分客户端会报协议错误。
@app.delete("/items/{item_id}", tags=["商品"], status_code=status.HTTP_204_NO_CONTENT, summary="删除商品")
def delete_item(item_id: int) -> Response:
    """删除商品，返回 204。

    【注意】`status_code=204` 只是声明，真正的空响应体靠返回空的 `Response` 实现。
    """
    DB.pop(item_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# 关键点 3：@app.get 不会自动支持 HEAD
# ============================================================
# 【作用】用两个装饰器让同一个函数同时响应 GET 与 HEAD
# 【为什么】监控探针常用 HEAD 只取响应头；若只有 GET，探针会拿到 405
# 【注意】不要用 `api_route(methods=["GET", "HEAD"])` 一口气注册：FastAPI 会为每个方法
#        生成 operation_id（如 health_health_get），两个方法同名会触发
#        UserWarning: Duplicate Operation ID。把 HEAD 设为 include_in_schema=False 更干净。
@app.get("/health", tags=["运维"], summary="健康检查")
@app.head("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


# ============================================================
# 关键点 4：路径转换器
# ============================================================
# 【作用】`{file_path:path}` 允许匹配包含 `/` 的剩余路径
# 【注意】`:path` 会吃掉后面所有段，所以它之后的路由基本不会命中，必须放最后
@app.get("/files/{file_path:path}", tags=["文件"], summary="按路径取文件")
def read_file(file_path: str) -> dict[str, str]:
    """演示 `:path` 转换器。`/files/a/b/c.txt` 会得到 `file_path="a/b/c.txt"`。"""
    return {"path": file_path}


# ============================================================
# 关键点 5：路由可见性
# ============================================================
@app.get("/internal/debug", include_in_schema=False)
def debug_info() -> dict[str, int]:
    """内部调试接口：可访问，但不出现在 /docs 与 openapi.json 里。

    【注意】`include_in_schema=False` 只是「文档不可见」，**不是安全措施**——
           知道路径的人照样能访问。真正的保护要靠鉴权（第 46 章）。
    """
    return {"items": len(DB)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
