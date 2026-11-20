# 66 配置管理

## 一句话结论

配置用一个 `BaseSettings` 子类声明，优先级是 **环境变量 > `.env` 文件 > 类默认值**（实测 `APP_MAX_ITEMS=9` 覆盖 `.env` 里的 `7`）。用 `env_prefix="APP_"` 加命名空间，避免和系统的 `DEBUG`、`PATH` 撞车（实测不带前缀的 `DEBUG=false` **不生效**）。密钥用 `SecretStr`，`str`/`repr`/`model_dump(mode="json")` 三处都是 `**********`。两个坑：`extra="forbid"` **只对 `.env` 文件生效**，环境变量里多余的 `APP_FOO` 会被静默忽略；`lru_cache` 做单例，改环境后必须 `cache_clear()`。

## 最小可运行案例

```python
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="forbid",
    )

    env: Literal["dev", "prod"] = "dev"
    debug: bool = True
    database_url: str = "sqlite:///./app.db"
    secret_key: SecretStr = SecretStr("dev-only")
    max_items: int = Field(default=100, ge=1, le=10_000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

端点注入：

```python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()
SettingsDep = Annotated[Settings, Depends(get_settings)]


@app.get("/config")
def read_config(settings: SettingsDep) -> dict:
    return {"env": settings.env, "secret": str(settings.secret_key)}
```

## 怎么跑

```powershell
cd "11-应用结构\66-配置管理\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 默认值 -> dev/True/100
[PASS] 环境变量覆盖 -> prod/False/5
[PASS] .env 读取 -> prod/False/7
[PASS] 环境变量优先 -> 9 覆盖 7
[PASS] 密钥脱敏 -> str/repr/dump 均为 **********
[PASS] 枚举校验 -> staging → literal_error
[PASS] 范围校验 -> 0 → greater_than_equal
[PASS] .env 未知字段 -> extra_forbidden at ('app_unknown',)
[PASS] 环境变量未知被忽略 -> APP_FOO 被静默忽略
[PASS] 前缀必需 -> DEBUG 不生效，debug 仍为 True
[PASS] 单例 -> 同环境同一对象
[PASS] 依赖注入 -> 端点读到 prod/2
[PASS] 健康检查切换 -> debug 有 detail，prod 无
[PASS] 缺文件不报错 -> 缺文件 → 用默认值

结果：14/14 通过
```

## 核心 API 速查

| 项 | 写法 | 作用 |
| --- | --- | --- |
| 基类 | `BaseSettings` | 从环境读字段 |
| 配置 | `SettingsConfigDict(...)` | 文件、前缀、严格模式 |
| `env_file` | `".env"` | 文件路径 |
| `env_prefix` | `"APP_"` | 命名空间 |
| `extra` | `"forbid"` | 拒绝未知字段（仅文件）|
| `case_sensitive` | `False`（默认）| 大小写不敏感 |
| 密钥 | `SecretStr` | 自动脱敏 |
| 校验 | `Field(ge=..., le=...)` | 范围 |
| 枚举 | `Literal["dev","prod"]` | 限定取值 |
| 单例 | `@lru_cache` | 只读一次文件 |

| 优先级 | 来源 |
| --- | --- |
| 最高 | 环境变量 `APP_*` |
| 中 | `.env` 文件 |
| 最低 | 类默认值 |

| 实测 | 值 |
| --- | --- |
| `APP_ENV=staging` | `literal_error` |
| `APP_MAX_ITEMS=0` | `greater_than_equal` |
| `.env` 里 `APP_UNKNOWN` | `extra_forbidden` at `('app_unknown',)` |
| 环境变量 `APP_FOO` | 静默忽略 |
| 环境变量 `DEBUG` | 不生效 |
| `SecretStr` | `**********` |
| 缺 `.env` | 不报错 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 全局 `settings = Settings()` | 测试无法替换 | `Depends(get_settings)` |
| 不加 `env_prefix` | 与系统 `DEBUG` 冲突 | `APP_` 前缀 |
| 明文 `str` 密钥 | 日志泄露 | `SecretStr` |
| 把 `.env` 提交仓库 | 密钥泄露 | `.gitignore` + `.env.example` |
| 改环境后不 `cache_clear` | 读到旧配置 | 测试里清缓存 |
| 以为 `extra="forbid"` 管环境变量 | 多余的 `APP_*` 静默忽略 | 只防文件拼写 |
| 用 `os.environ` 直接读 | 无校验、无默认、散落各处 | 统一 `Settings` |
| `Literal` 写成 `str` | 非法值能进 | 用 `Literal`/`Enum` |
| 配置在 import 时就实例化 | `.env` 未就绪就报错 | 延迟到 `get_settings()` |
| 数字用 `str` | 参与运算报错 | `int`/`bool` 由 pydantic 转 |
| `bool` 用 `"yes"` | 解析失败或误判 | `true/false/1/0` |
| 生产用 `dev` 默认值 | 调试信息外泄 | 显式设 `APP_ENV` |
| 配置对象当全局单例跨进程共享 | 多 worker 各自一份 | 每进程各读一次 |
| 热更新配置 | `lru_cache` 不刷新 | 重启或显式清缓存 |

## 毕业自查

- [ ] 能写出 `Settings` 类与 `get_settings()`
- [ ] 能说清三级优先级
- [ ] 能解释 `env_prefix` 的必要性
- [ ] 能证明 `SecretStr` 不泄露
- [ ] 知道 `extra="forbid"` 的作用范围
- [ ] 动手题一：加 `DatabaseSettings` 嵌套配置
- [ ] 动手题二：在测试里 override `get_settings` 换成假配置

> 想看嵌套配置、`Secrets` 目录挂载、多环境文件、热加载、12-Factor、18 条坑，继续读 [`base.md`](./base.md)。