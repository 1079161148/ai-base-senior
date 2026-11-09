"""时间处理的唯一入口。

**全项目的三条约定**：

| 环节 | 用什么 | 理由 |
|---|---|---|
| 写入数据库 | 恒为 UTC 的 ISO 字符串 | 时刻唯一，换服务器时区也不会变含义 |
| 对外传输 | 带时区偏移的 ISO 8601 | 任何语言、任何时区都能正确解析 |
| 页面展示 | 用户浏览器的本地时区 | 用户只关心"我这儿几点" |

**为什么要集中在这里**：

如果每个模型、每个 service 各自 `datetime.now().isoformat()`，很快就会出现
「有人存本地时间、有人存 UTC，有人带毫秒、有人不带，有人带时区、有人不带」，
同一套系统里冒出三种时间格式，之后任何按时间排序/比较的地方都会出错。

所以：**业务代码只允许用 `now()` 取时间、用 `UtcDatetime` 声明字段，不许自己格式化。**

> 换算关系示例（北京时间 UTC+8）：
> 存库 `2026-11-08T15:01:27+00:00` → 页面显示 `2026-11-08 23:01`
"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer

from .config import settings


def now() -> datetime:
    """当前时刻（带 UTC 时区）。

    业务层不要写 `datetime.now()` —— 那是 naive 值，没有时区信息，
    换个部署环境含义就变了。统一走这里。
    """
    return datetime.now(UTC)


def _ensure_aware(dt: datetime) -> datetime:
    """把无时区的 naive 值按 UTC 解释。

    历史数据（早期用 `datetime.now()` 写入的）没有时区，
    直接 `astimezone()` 会按服务器本地时区猜，导致整体偏移 8 小时。
    统一补上 UTC 更安全，也比让整条记录报错好。
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _serialize(dt: datetime) -> str:
    """datetime → 对外 JSON 字符串。**全项目唯一的时间输出格式。**

    秒级精度就够了：待办列表不需要微秒。

    `settings.TIME_OUTPUT_UTC = False` 时转为服务器本地时区，
    便于单时区团队在 Swagger / 日志里肉眼核对。
    """
    aware = _ensure_aware(dt)
    target = aware.astimezone(UTC) if settings.TIME_OUTPUT_UTC else aware.astimezone()

    if settings.TIME_FORMAT == "human":
        # 「2026-11-08 23:10:33」—— 没有 T、没有时区后缀，肉眼最舒服。
        # 代价：丢掉了时区信息，前端按本地时区猜；跨时区用户会看到错的时间。
        return target.strftime("%Y-%m-%d %H:%M:%S")

    return target.isoformat(timespec="seconds")


# 在 Pydantic 模型里这样声明字段：`created_at: UtcDatetime`
# 序列化规则只写一次，以后新增 updated_at / deleted_at / expires_at 都不用再管格式。
UtcDatetime = Annotated[
    datetime,
    PlainSerializer(_serialize, return_type=str, when_used="json"),
]


def to_storage(dt: datetime) -> str:
    """datetime → 数据库里存的字符串（恒为 UTC，不随 TIME_OUTPUT_UTC 变化）。"""
    return _ensure_aware(dt).astimezone(UTC).isoformat(timespec="seconds")


def from_storage(value: str | datetime) -> datetime:
    """数据库里的值 → 带时区的 datetime。

    兼容两种历史数据：带时区的新数据、不带时区的旧数据。
    """
    if isinstance(value, datetime):
        return _ensure_aware(value)
    return _ensure_aware(datetime.fromisoformat(value))
