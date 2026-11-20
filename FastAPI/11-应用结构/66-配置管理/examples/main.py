"""第 66 章 · 配置管理。

启动：uvicorn main:app --reload
验收：python verify.py

【要点】配置通过依赖注入进端点，而不是 `import settings` 全局变量：
        依赖可以 override，测试时能换成假配置。
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI

from config import Settings, get_settings

app = FastAPI(title="第 66 章 · 配置管理", version="0.1.0")

SettingsDep = Annotated[Settings, Depends(get_settings)]


@app.get("/config", tags=["配置"], summary="脱敏后的配置")
def read_config(settings: SettingsDep) -> dict[str, Any]:
    """【实测】`str(SecretStr)` 是 `**********`，可以安全返回"""
    return {
        "env": settings.env,
        "debug": settings.debug,
        "database_url": settings.database_url,
        "secret_key": str(settings.secret_key),
        "max_items": settings.max_items,
    }


@app.get("/config/raw", tags=["配置"], summary="整个 dump（看是否会泄露）")
def read_raw(settings: SettingsDep) -> dict[str, Any]:
    """【实测】`model_dump(mode="json")` 对 `SecretStr` 仍是 `**********`"""
    return settings.model_dump(mode="json")


@app.get("/health", tags=["诊断"], summary="按环境返回不同细节")
def health(settings: SettingsDep) -> dict[str, Any]:
    """【要点】生产环境不暴露内部地址"""
    body: dict[str, Any] = {"status": "ok", "env": settings.env}
    if settings.debug:
        body["detail"] = {"database_url": settings.database_url}
    return body


@app.get("/items", tags=["业务"], summary="受配置影响的端点")
def list_items(settings: SettingsDep) -> dict[str, Any]:
    """【作用】演示业务参数来自配置"""
    return {"limit": settings.max_items, "items": ["a", "b", "c"][: settings.max_items]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)