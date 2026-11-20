"""第 66 章 · 自动验收。运行：python verify.py"""

import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import config as config_module  # noqa: E402
import main  # noqa: E402
from config import Settings, get_settings  # noqa: E402


def clear_app_env() -> None:
    for key in [key for key in os.environ if key.upper().startswith("APP_")]:
        os.environ.pop(key, None)
    get_settings.cache_clear()


@contextmanager
def env(**values: str) -> Iterator[None]:
    """【作用】临时改环境变量，退出时还原并清缓存"""
    saved = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


@contextmanager
def dotenv(content: str) -> Iterator[str]:
    """【作用】写一个临时 `.env`，退出时删除"""
    handle = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8")
    handle.write(content)
    handle.close()
    try:
        yield handle.name
    finally:
        os.unlink(handle.name)


def client() -> TestClient:
    return TestClient(main.app)


def check_defaults() -> str:
    """无任何外部配置时用类默认值。"""
    with env():
        settings = Settings(_env_file=None)
    assert settings.env == "dev", settings.env
    assert settings.debug is True, settings.debug
    assert settings.max_items == 100, settings.max_items
    assert settings.database_url == "sqlite:///./app.db", settings.database_url
    return "dev/True/100"


def check_env_overrides() -> str:
    """环境变量覆盖默认值。"""
    with env(APP_ENV="prod", APP_DEBUG="false", APP_MAX_ITEMS="5"):
        settings = Settings(_env_file=None)
        assert settings.env == "prod", settings.env
        assert settings.debug is False, settings.debug
        assert settings.max_items == 5, settings.max_items
    return "prod/False/5"


def check_dotenv_loaded() -> str:
    """`.env` 文件被读取。"""
    with env(), dotenv("APP_ENV=prod\nAPP_DEBUG=false\nAPP_MAX_ITEMS=7\n") as path:
        settings = Settings(_env_file=path)
        assert (settings.env, settings.debug, settings.max_items) == ("prod", False, 7), settings
    return "prod/False/7"


def check_env_beats_dotenv() -> str:
    """环境变量优先于 `.env`。"""
    with env(APP_MAX_ITEMS="9"), dotenv("APP_MAX_ITEMS=7\n") as path:
        settings = Settings(_env_file=path)
    assert settings.max_items == 9, settings.max_items
    return "9 覆盖 7"


def check_secret_masked() -> str:
    """`SecretStr` 三处都不泄露明文。"""
    with env(APP_SECRET_KEY="super-secret-value"):
        settings = Settings(_env_file=None)
        assert str(settings.secret_key) == "**********", str(settings.secret_key)
        assert "super-secret-value" not in repr(settings.secret_key), repr(settings.secret_key)
        dumped = settings.model_dump(mode="json")
        assert dumped["secret_key"] == "**********", dumped
        assert "super-secret-value" not in str(dumped), dumped
        assert settings.secret_key.get_secret_value() == "super-secret-value"
    return "str/repr/dump 均为 **********"


def check_literal_validation() -> str:
    """`env` 只接受 dev/prod。"""
    with env(APP_ENV="staging"):
        try:
            Settings(_env_file=None)
        except ValidationError as exc:
            assert exc.errors()[0]["type"] == "literal_error", exc.errors()
            return "staging → literal_error"
    raise AssertionError("staging 居然通过了")


def check_range_validation() -> str:
    """`max_items` 有上下界。"""
    with env(APP_MAX_ITEMS="0"):
        try:
            Settings(_env_file=None)
        except ValidationError as exc:
            assert exc.errors()[0]["type"] == "greater_than_equal", exc.errors()
            return "0 → greater_than_equal"
    raise AssertionError("0 居然通过了")


def check_extra_in_dotenv_forbidden() -> str:
    """`.env` 里的未知字段 → `extra_forbidden`。"""
    with env(), dotenv("APP_UNKNOWN=1\n") as path:
        try:
            Settings(_env_file=path)
        except ValidationError as exc:
            error = exc.errors()[0]
            assert error["type"] == "extra_forbidden", error
            assert error["loc"] == ("app_unknown",), error
            return f'extra_forbidden at {error["loc"]}'
    raise AssertionError("未知字段居然被接受")


def check_extra_env_ignored() -> str:
    """**实测坑**：环境变量里的未知 `APP_*` 被忽略，不报错。"""
    with env(APP_FOO="1"):
        settings = Settings(_env_file=None)
    assert settings.env == "dev", settings.env
    return "APP_FOO 被静默忽略"


def check_prefix_required() -> str:
    """不带前缀的 `DEBUG` 不生效。"""
    with env(DEBUG="false"):
        settings = Settings(_env_file=None)
    assert settings.debug is True, settings.debug
    return "DEBUG 不生效，debug 仍为 True"


def check_singleton() -> str:
    """`lru_cache` 保证同一实例。"""
    with env():
        first = get_settings()
        second = get_settings()
        assert first is second, (id(first), id(second))
    with env(APP_ENV="prod"):
        third = get_settings()
        assert third is not first, "cache 没清"
    return "同环境同一对象"


def check_di_injection() -> str:
    """端点通过 `Depends(get_settings)` 拿到配置。"""
    with env(APP_ENV="prod", APP_MAX_ITEMS="2"):
        with client() as c:
            body = c.get("/config").json()
    assert body["env"] == "prod", body
    assert body["max_items"] == 2, body
    assert body["secret_key"] == "**********", body
    return "端点读到 prod/2"


def check_health_switches() -> str:
    """`debug` 决定是否暴露内部地址。"""
    with env(APP_DEBUG="true"):
        with client() as c:
            debug_body = c.get("/health").json()
    with env(APP_DEBUG="false"):
        with client() as c:
            prod_body = c.get("/health").json()
    assert "detail" in debug_body, debug_body
    assert "detail" not in prod_body, prod_body
    return "debug 有 detail，prod 无"


def check_missing_dotenv_ok() -> str:
    """`.env` 不存在不报错。"""
    settings = Settings(_env_file="definitely-missing.env")
    assert settings.env == "dev", settings.env
    return "缺文件 → 用默认值"


CHECKS = [
    ("默认值", check_defaults),
    ("环境变量覆盖", check_env_overrides),
    (".env 读取", check_dotenv_loaded),
    ("环境变量优先", check_env_beats_dotenv),
    ("密钥脱敏", check_secret_masked),
    ("枚举校验", check_literal_validation),
    ("范围校验", check_range_validation),
    (".env 未知字段", check_extra_in_dotenv_forbidden),
    ("环境变量未知被忽略", check_extra_env_ignored),
    ("前缀必需", check_prefix_required),
    ("单例", check_singleton),
    ("依赖注入", check_di_injection),
    ("健康检查切换", check_health_switches),
    ("缺文件不报错", check_missing_dotenv_ok),
]


def run() -> int:
    clear_app_env()
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    clear_app_env()
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())