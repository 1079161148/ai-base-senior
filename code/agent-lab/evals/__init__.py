"""S7 · 评测体系。

四个模块各管一件事，别混：
    dataset.py  读并校验评测集（数据质量先于评测方法）
    runner.py   跑一条用例，收集答案/工具/延迟/成本
    judge.py    判分（规则 / LLM-as-Judge / 对抗校验）
    report.py   聚合四指标 + 失败归类 + 门禁
"""
