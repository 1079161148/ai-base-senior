# 所有常用命令收口在这里：新人只需要记 `make` 子命令
.PHONY: install run test verify migrate seed clean

install:            ## 安装依赖（含 dev）
	uv sync

run:                ## 本地开发，热重载
	uv run uvicorn app.main:app --reload --port 8000

test:               ## 跑测试
	uv run pytest -q

verify:             ## 跑 12 块积木验收
	uv run python verify.py

migrate:            ## 只跑迁移，不启动服务
	uv run python -m app.db.migrate

seed:               ## 灌种子数据
	uv run python scripts/seed.py

clean:              ## 清掉本地库与缓存
	rm -f app.db && find . -name __pycache__ -type d -exec rm -rf {} +