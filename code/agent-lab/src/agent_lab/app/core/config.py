"""全局配置。

所有可变的东西（模型名、单价、超时、跨域白名单）都放这里，
业务代码只 import settings，不要读 os.environ。
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：core → app → agent_lab → src → agent-lab
# 等价于 `Path(__file__).parents[4]`，字符串人读得懂，所以写全链路。
#
# **为什么不用 env_file=".env"**：
# 相对路径是相对「进程工作目录」解析的。从别的目录启动
# （`uv run --directory ...`、IDE 的运行配置、systemd、Docker）
# 就找不到 .env，而 pydantic-settings 对「文件不存在」**不报错**，
# 只是静默用默认值 —— 表现为「API Key 明明写了却一直是空的」。
# 这种 bug 排查成本极高，所以改成基于本文件位置的绝对路径。
#
# 部署到容器时通常直接注环境变量，此路径不存在也无害。
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    # model_config 是 Pydantic 的「类级配置」，不是实例字段。
    # ClassVar 明确告诉类型检查器「它不属于模型的字段」，
    # 不加注解会触发 basedpyright 的「未注解类属性」告警（因为本类没加 @final）。
    # 类型必须与基类完全一致（ClassVar 是不变的，写窄了会被判为不兼容覆写）：
    # BaseSettings.model_config 声明为 ClassVar[SettingsConfigDict]，这里照抄。
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 应用 ---
    PROJECT_NAME: str = "agent-lab"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- S9：鉴权与多租户 ---
    # 关掉之后所有请求都算作 demo 用户，方便本地调 Swagger / 跑脚本。
    # 对外部署必须开（compose 里已显式设为 true）。
    AUTH_ENABLED: bool = True
    # HS256 的对称密钥。**上线前必须换成随机长串**：
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    # 用默认值等于没有鉴权 —— 任何看过源码的人都能自己签一个 token。
    AUTH_SECRET: str = "dev-only-change-me-in-production"
    # token 有效期。7 天是「免登录体验」和「泄露后损失可控」的折中。
    AUTH_TOKEN_TTL_SECONDS: int = 7 * 24 * 3600
    # 启动时自动建演示账号。学习/演示环境设为 true，
    # 生产应关掉并改用 create_user 脚本 —— 默认密码进生产是常见事故。
    SEED_DEMO_USER: bool = True
    DEMO_USERNAME: str = "demo"
    DEMO_PASSWORD: str = "demo123"

    # --- 本地模型（RAG 的嵌入 / 重排） ---
    # 模型从 HuggingFace 下载。国内直连 huggingface.co 基本必然超时，
    # 表现为启动日志里刷 "Could not download model ... sleeping for 9.0 seconds"。
    # hf-mirror.com 是社区维护的镜像（同协议，换个域名即可）。
    # 置空表示直连官方站。
    HF_ENDPOINT: str = "https://hf-mirror.com"

    # 模型缓存目录。默认放项目 data/ 下，两个原因：
    #   1. fastembed 默认缓存到 %TEMP%\fastembed_cache，Windows 磁盘清理
    #      和重启都可能清掉它 —— 下次启动就重新下载几百 MB，国内还可能下不动。
    #   2. data/ 已经挂进 docker volume，重建容器不用重下模型。
    MODEL_CACHE_DIR: str = str(_PROJECT_ROOT / "data" / "models")

    # Cross-encoder 重排开关。默认关闭，两个原因：
    #   1. 模型（bge-reranker-base ONNX）约 1.1GB，首次启用要下载，
    #      国内走镜像也得几分钟；
    #   2. 候选数只有个位数时它几乎不改变排序，却要多花几百毫秒到几秒。
    # 什么时候该开：知识库上万块、混合检索的 top-k 里明显混着不相关的结果。
    RERANK_ENABLED: bool = False

    # 送进 cross-encoder 的候选数量。粗筛（向量 50 + BM25 50）融合后取这么多，
    # 再精排到 top_k。太小覆盖不到正确答案，太大则每个 pair 都要过一次模型，
    # 推理时间线性增长。
    RERANK_CANDIDATES: int = 20

    # --- 路由 ---
    # 所有业务接口统一挂在这个前缀下，方便以后做版本并存
    API_V1_PREFIX: str = "/api/v1"

    # --- 跨域 ---
    # 必须是具体地址。浏览器不允许 allow_origins=["*"] 与 allow_credentials=True 同时生效
    # 前端 dev server 跑在 9999（见 agent-lab-web/vite.config.ts）。
    # 开发时请求都走 vite 代理，属于同源，本来不触发 CORS；
    # 这里保留是为了直连 8001 调试时不被拦。
    CORS_ORIGINS: list[str] = [
        "http://localhost:9999",
        "http://127.0.0.1:9999",
    ]

    # --- 时间 ---
    # 对外 JSON 里时间用哪个时区显示：
    #   True  = UTC（推荐）。时刻唯一，跨时区、多服务器部署都不会错。
    #   False = 服务器本地时区。Swagger 里看着顺眼，但依赖部署机器的 tz 配置。
    # 注意：这只影响「输出格式」，数据库里永远存 UTC。
    # 想改成本地时间：在 .env 里写 TIME_OUTPUT_UTC=false
    TIME_OUTPUT_UTC: bool = True

    # 时间的序列化格式：
    #   iso   = 2026-11-08T23:10:33+08:00   （国际标准，任何语言都能解析，推荐）
    #   human = 2026-11-08 23:10:33         （给人看舒服，但非标准）
    #
    # 只有调试期建议用 human：去掉 T 和时区后，浏览器只能按本地时区猜，
    # 跨时区用户会看到错误时间。上线前请改回 iso。
    TIME_FORMAT: Literal["iso", "human"] = "iso"

    # --- 大模型（S1）---
    # 统一走 **OpenAI 兼容协议**（POST {base_url}/chat/completions + stream）。
    # 这样同一个实现能覆盖绝大多数厂商，只改这三项即可切换：
    #
    #   DeepSeek   https://api.deepseek.com/v1              deepseek-chat
    #   OpenAI     https://api.openai.com/v1                gpt-4o-mini
    #   通义千问   https://dashscope.aliyuncs.com/compatible-mode/v1   qwen-plus
    #   Kimi       https://api.moonshot.cn/v1               moonshot-v1-8k
    #   智谱       https://open.bigmodel.cn/api/paas/v4     glm-4-flash
    #   本地 Ollama http://127.0.0.1:11434/v1                qwen2.5:7b
    #
    # Anthropic 的协议不兼容（/v1/messages + 事件流格式不同），
    # 要接它需要另写适配器 —— 留到以后，不在 S1 里堆复杂度。
    #
    # 留空 = 未配置。此时接口返回明确的 LLM_NOT_CONFIGURED，
    # 而不是 500 或一直挂起，前端的报错信息能直接告诉用户「去填哪一项」。
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"

    # 超时拆成两段（httpx.Timeout 的语义）：
    #   connect 短一点：连不上要立刻反馈，别让用户干等
    #   read    长一点：模型吐字慢，首个 token 可能要等十几秒
    LLM_CONNECT_TIMEOUT: float = 10.0
    LLM_READ_TIMEOUT: float = 60.0

    # 单次回复上限。不设的话模型可能一口气生成几千 token，
    # 既慢又贵，前端也会滚半天。
    #
    # 推理模型（DeepSeek-R1 系、QwQ、o1 等）**思考过程也算 token**，
    # 一次简单的问答就可能先烧掉几百个。设成 1024 时，答案常被截断成半句话。
    # 2048 对这类模型是更实际的起点。
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.7

    # --- 成本计量（S2）---
    # 单价单位：**人民币元 / 每百万 token**。
    # 各家差异极大，必须按自己平台的账单填，否则算出来的数字只是"看起来像真的"。
    #
    # 参考量级（元/百万 token）：
    #   国产轻量模型   输入 1～2    输出 2～8
    #   GPT-4o 级别    输入 18      输出 72
    #   中转站          以控制台标价为准，通常低于官方
    #
    # 填 0 等于关掉成本刹车（只剩步数刹车），慎用 —— 那意味着账单无上限。
    LLM_PRICE_INPUT_PER_1M: float = 1.0
    LLM_PRICE_OUTPUT_PER_1M: float = 2.0

    # 单次任务成本上限（元）。超了立刻停，不再继续调模型。
    # 0.5 元对个人学习项目足够宽松：一次普通对话通常在 0.001 元量级，
    # 真撞到 0.5 多半是循环失控了。
    LLM_MAX_COST_CNY: float = 0.5

    # 单个工具执行超时（秒）。工具内部可能调外部 API，
    # 不设超时的话，一个卡住的请求会把整轮对话永久拖住。
    TOOL_TIMEOUT_SECONDS: float = 10.0

    # --- S6：结构化输出 ---
    # 模型输出不符合 schema 时的最大尝试次数（含首次）。
    # 每次都把 Pydantic 的具体错误回灌给模型让它改；
    # 3 次还改不对，说明是提示词或 schema 设计有问题，继续重试只是烧钱。
    STRUCTURED_MAX_ATTEMPTS: int = 3
    # 结构化输出的温度。默认 0 —— 要的是稳定可解析，不是文采。
    STRUCTURED_TEMPERATURE: float = 0.0

    # --- S8：护栏与配额 ---
    # 单条输入上限。比 ChatRequestV2 的 8000 更严：
    # 8000 是"协议上限"，4000 是"经济上限"——长输入 token 成本会成倍上升。
    GUARD_MAX_INPUT_CHARS: int = 4000
    # 命中高危注入模式时直接拦截（False 则只标记、继续走但加固提示）
    GUARD_BLOCK_ON_INJECTION: bool = True

    # 限流：每个来源每分钟允许的请求数（内存令牌桶，单实例有效）
    RATE_LIMIT_PER_MINUTE: int = 20
    # 同时在跑的生成任务上限，超过直接 429 —— 保护模型账号和本机 CPU
    MAX_CONCURRENT_REQUESTS: int = 8

    # 日成本上限（元）。超过后所有请求降级拒绝，第二天自动恢复。
    # 这是"成本攻击"的最后一道闸：前面单次成本上限挡不住高频小请求。
    DAILY_COST_LIMIT_CNY: float = 5.0

    # --- pgvector（S3）---
    # docker compose up -d 后自动可用。
    # 端口 5433 是因为本机已有另一个 PostgreSQL 占着 5432。
    PG_DSN: str = "postgresql://agent_lab:agent_lab@127.0.0.1:5433/agent_lab"
    PG_MIN_SIZE: int = 2
    PG_MAX_SIZE: int = 6

    # --- S4：记忆与上下文预算 ---
    # 上下文预算（token 数）。教材建底座 8000，对应本地模型的典型窗口。
    CONTEXT_BUDGET: int = 8000
    # 工作记忆保留最近 N 轮。超出的由摘要记忆接管。
    WORKING_MEMORY_ROUNDS: int = 5
    # 摘要触发阈值：工作记忆占用超过预算的这个比例时，压缩旧轮次
    SUMMARY_TRIGGER_RATIO: float = 0.75
    # 长期记忆写入阈值：scan_relevance 得分低于此值的不存
    LONG_TERM_MIN_SCORE: float = 0.6
    # 长期记忆检索数量
    LONG_TERM_TOP_K: int = 3

    def cost_of(self, prompt_tokens: int, completion_tokens: int) -> float:
        """按 token 数换算一次调用的成本（元）。

        放在配置里而不是各调用点：价格一改，全项目的成本数字自动同步。
        """
        return (
            prompt_tokens * self.LLM_PRICE_INPUT_PER_1M
            + completion_tokens * self.LLM_PRICE_OUTPUT_PER_1M
        ) / 1_000_000

    @property
    def llm_configured(self) -> bool:
        """是否配好了调用模型所需的最小信息。

        property 而不是普通字段：它由另外三项推导而来，
        存成字段会出现「改了 KEY 但 configured 还是旧值」的不一致。
        """
        return bool(self.LLM_API_KEY.strip() and self.LLM_BASE_URL.strip() and self.LLM_MODEL.strip())


@lru_cache
def get_settings() -> Settings:
    """缓存实例，整个进程只解析一次环境变量。"""
    return Settings()


settings = get_settings()


# huggingface_hub 在**模块导入时**读取 HF_ENDPOINT 环境变量并缓存成模块常量，
# 之后再改 os.environ 就不生效了。所以必须在这里（settings 刚解析完、
# 而 fastembed 还没被任何模块导入的时刻）把它写进进程环境。
#
# 这也解释了为什么 embedder 里的 fastembed 必须惰性导入：
# 只要有一处写了模块级 `from fastembed import TextEmbedding`，
# 导入顺序稍有不同就会在写入 HF_ENDPOINT 之前把 huggingface_hub 拉起来。
if settings.HF_ENDPOINT:
    os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
