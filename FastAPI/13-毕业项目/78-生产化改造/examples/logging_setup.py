"""日志配置：一行一请求，带请求 ID。

【要点】`force=True` 保证重复配置（测试里多次 import/重载）不会叠加 handler。
"""

import logging


class RequestIdFilter(logging.Filter):
    """没有 `request_id` 的日志补 `-`，避免格式化抛 KeyError"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT, datefmt="%H:%M:%S"))
    handler.addFilter(RequestIdFilter())

    logging.basicConfig(level=level, handlers=[handler], force=True)
    # 第三方库的访问日志与我们的重复，压低到 WARNING
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)