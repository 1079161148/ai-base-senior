"""积木 10 · 日志：一行一请求，带 request_id。"""

import logging


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT, datefmt="%H:%M:%S"))
    handler.addFilter(RequestIdFilter())
    # force=True：重复调用不叠加 handler（测试里会多次建 app）
    logging.basicConfig(level=level, handlers=[handler], force=True)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)