# Token 统计（Token Counting）

> **权威依据**
> ① **Anthropic**《Token counting》官方文档 — `POST /v1/messages/count_tokens`
> ② **tiktoken**（OpenAI 官方分词库）
> ③ **Hugging Face transformers** — `AutoTokenizer`
> ④ **Google Gemini / Vertex AI** — `countTokens` API
> ⑤ **Moonshot AI** — `estimate-token-count`
> ⑥ 本文笔记：事前统计 / 事后统计的工程分类

## 结论

**Token 统计是把文本序列转换成 Token 数量的过程。**

工程上它分成两类，**用途完全不同，绝不可混用**：

| 类型 | 时机 | 用途 | 能否用于计费 |
|------|------|------|-------------|
| **事前统计** | 发请求**之前** | 拦截、预校验、报价、路由 | ❌ **不能** |
| **事后统计** | 发请求**之后** | 计费、对账、可观测 | ✅ **唯一可信** |

**一句话铁律**：

> **事前统计是"估算"（estimate），不是"账单"。收费必须用服务商返回的 `usage`。**

## 一、先搞懂：Token 是什么

### 1.1 不是字符，也不是词

**Token 是分词器（tokenizer）切出来的最小单位**——介于"字符"和"词"之间。

| 语言 | 大致规律 |
|------|----------|
| **英文** | 常见词 = 1 token；生僻/长词被拆成多段；**约 4 字符 ≈ 1 token** |
| **中文** | 汉字通常 1 字 ≈ 1–2 token（**远不如英文经济**） |
| **代码** | 缩进、标点、变量名碎得厉害，token 效率偏低 |

> Google 官方给出的经验值：**1 token ≈ 4 个英文字符，100 token ≈ 60–80 个英文单词。**

### 1.2 底层是 BPE（Byte Pair Encoding）

```
原始文本 → 按字节/字符拆 → 反复合并最高频的相邻对 → 得到词表
```

**关键推论**：**词表由训练语料决定**，所以——

> **同一段文字，在不同模型上 token 数必然不同。**

这不是"精度问题"，而是**根本性的**：GPT 的词表和 Qwen 的词表是**两套不同的东西**。

### 1.3 一个实测感受

同样那句测试文本：

```
人工智能正在深刻改变我们的生活，从智能助手到自动驾驶，AI 无处不在。
```

| 分词器 | Token 数（约） |
|--------|---------------|
| `gpt-4o`（o200k_base） | 30 上下 |
| `DeepSeek-V3` | 20 上下 |
| 纯英文等价句 | 15 上下 |

> **中文的 token 成本是英文的 1.5–2 倍**——这是中文产品做成本估算时最容易低估的一项。

## 二、事前统计 vs 事后统计

### 2.1 对照表

| 维度 | 事前统计 | 事后统计 |
|------|----------|----------|
| **时机** | 调用前 | 调用后 |
| **数据来源** | 本地分词 / 服务商计数接口 | 响应中的 `usage` 字段 |
| **准确性** | **估算**，有偏差 | **精确**，即账单 |
| **成本** | 计入限流，但多数免费 | 无额外成本 |
| **额外延迟** | 有（分 token 要算） | 无 |
| **能防的事** | 超长、超预算、超额度 | 什么也防不了（已发生） |

### 2.2 两者的正确分工

```
                ┌─── 事前统计 ───┐        ┌─── 事后统计 ───┐
用户请求 → 拦截/预校验/报价 → API 调用 → 拿到 usage → 计费/对账
                └────────────────┘        └────────────────┘
                     防浪费                   收钱
```

> **事前统计省的是"无效调用"，事后统计算的是"真实成本"。**

## 三、事后统计：唯一的计费依据

### 3.1 标准做法

模型服务商的 API 响应里都会带 `usage`：

```python
resp = client.chat.completions.create(...)

usage = resp.usage
print(usage.prompt_tokens)      # 输入
print(usage.completion_tokens)  # 输出
print(usage.total_tokens)       # 合计
```

### 3.2 各家字段名对照

| 厂商 | 输入 | 输出 | 备注 |
|------|------|------|------|
| **OpenAI** | `prompt_tokens` | `completion_tokens` | 含 `prompt_tokens_details.cached_tokens` |
| **Anthropic** | `input_tokens` | `output_tokens` | 另有 `cache_creation_input_tokens` / `cache_read_input_tokens` |
| **Moonshot** | `prompt_tokens` | `completion_tokens` | 兼容 OpenAI 格式 |
| **DeepSeek** | `prompt_tokens` | `completion_tokens` | 含缓存命中字段 |

> **注意**：流式（stream）响应默认**不含 `usage`**。OpenAI 需显式传 `stream_options={"include_usage": True}`，Anthropic 在 `message_delta` 事件里给。**漏了这一项会导致"流式对话不算账"**——这是非常高频的生产事故。

## 四、事前统计的七种用途

你笔记里列的四种都很典型，我再补三种同样高频的。

### 4.1 单轮输入长度拦截

> 用户粘贴 10 万字合同，事前算出超 100k token，直接弹窗"文本过长，请分段上传"，**不发起无效 API 调用**。

**收益**：省一次昂贵调用 + 省用户等待 + 提示更友好。

### 4.2 用户额度 / 充值计费预校验

> 面向 C 端付费产品（AI 写作、AI 客服、知识库问答），调用前预计算预估总 token，若剩余额度不足直接拦截，提示充值。

**避免**：等 API 返回才告知超限——**用户已经等了 20 秒**。

### 4.3 企业预算前置审批

> 部门有月度 AI 成本预算。员工上传大文件跑分析前，本地算出预估 token，换算成人民币成本，超过阈值走审批。

### 4.4 报价前置展示

> SaaS 工具：用户上传文档后页面实时显示「本次预估消耗 XX token，约 XX 元」，确认后执行。

**收益**：**减少账单争议**——这是商业价值而非技术价值。

### 4.5 模型路由决策（补充）

```
预估 token < 8k   → 小模型（便宜、快）
预估 token < 128k → 中模型
预估 token > 128k → 大窗口模型 / 或先摘要
```

> Anthropic 官方文档明确把"**做出合理的模型路由决策**"列为 token 计数的用途之一。

### 4.6 上下文预算分配（补充）

Agent 场景的关键用途：

```
总窗口 200k
├── system prompt   2k
├── 工具定义        8k
├── 检索结果        ?   ← 用剩余额度倒推能塞多少
└── 对话历史        ?
```

> **不知道当前占了多少 token，就无法决定"还能检索多少条"。**

### 4.7 RAG 检索量控制（补充）

检索前先算 query + 已占用上下文，**倒推本次可以注入几个 chunk**，而不是固定 top-k。

## 五、事前统计的三种实现方式

### 5.1 方式一：服务商计数 API（最准，但有网络开销）

#### ① Anthropic 官方 count_tokens

**端点**：

```http
POST https://api.anthropic.com/v1/messages/count_tokens
x-api-key: $ANTHROPIC_API_KEY
content-type: application/json
anthropic-version: 2023-06-01
```

**Python SDK**：

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.count_tokens(
    model="claude-sonnet-4-5",
    system="You are a scientist",
    messages=[{"role": "user", "content": "Hello, Claude"}],
)
print(response.json())      # {"input_tokens": 14}
```

**关键特性（官方文档）**：

| 特性 | 说明 |
|------|------|
| **接受与创建消息相同的输入** | 含 `system`、`tools`、图片、PDF、`thinking` |
| **只返回 `input_tokens`** | **无法预估输出长度** |
| **完全免费** | 不产生费用 |
| **独立限流** | 与消息创建**各自计算 RPM**（Tier 1 = 100 RPM） |
| **≈ 估算值** | 官方明确说实际调用可能略有差异 |
| **不触发 prompt caching** | 传 `cache_control` 也无效，给的是**无缓存估算** |
| **含系统注入 token** | 但这部分**不计费** |

**两个必须知道的限制**：

1. **服务端工具（server tools）只计第一次采样调用** → 多轮工具循环的真实消耗**远高于**估值
2. **PDF 计数继承 Messages API 的全部 PDF 限制**

**扩展思考的计数规则**：

| 场景 | 是否计入 |
|------|----------|
| **之前**助手轮次的 thinking 块 | **忽略** |
| **当前**助手轮次的 thinking | **计入** |

#### ② Moonshot AI（你笔记里的方案）

```python
import os, requests
from dotenv import load_dotenv

load_dotenv('../.env')
API_KEY = os.environ.get("MOONSHOT_API_KEY")

url = "https://api.moonshot.cn/v1/tokenizers/estimate-token-count"

text = "人工智能正在深刻改变我们的生活，从智能助手到自动驾驶，AI 无处不在。"

response = requests.post(
    url,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "kimi-k3",
        "messages": [{"role": "user", "content": text}],
    },
)

result = response.json()
print(f"Token 数：{result['data']['total_tokens']}")
```

> **优点**：用的是**它自己的分词器**，比本地拿 tiktoken 猜准。
> **注意**：这是**估算接口**，返回 `total_tokens` 而非精确计费值。

#### ③ Google Gemini

**SDK**：`client.models.count_tokens(...)`，返回 `total_tokens`
**REST**：`models/{model}:countTokens`

> Gemini 官方经验值：**1 token ≈ 4 个英文字符**。

#### ④ 服务商计数 API 横向对比

| 厂商 | 端点 | 返回字段 | 费用 | 特点 |
|------|------|----------|------|------|
| **Anthropic** | `/v1/messages/count_tokens` | `input_tokens` | 免费 | 支持 tools/图片/PDF/thinking，独立限流 |
| **Moonshot** | `/v1/tokenizers/estimate-token-count` | `data.total_tokens` | 免费 | 兼容 messages 结构 |
| **Gemini** | `models/{model}:countTokens` | `totalTokens` | 免费 | 支持多模态 |
| **OpenAI** | **无官方计数端点** | — | — | 需用 tiktoken 本地算 |

> **重要**：OpenAI 目前**没有** count tokens 的 API，只能用 `tiktoken` 本地估算——**这是它与另外三家最大的差别**。

### 5.2 方式二：tiktoken（OpenAI 官方本地分词）

```python
import tiktoken

# 按模型名获取分词器
encoding = tiktoken.encoding_for_model("gpt-4o")

text = "人工智能正在深刻改变我们的生活，从智能助手到自动驾驶，AI 无处不在。"

tokens = encoding.encode(text)
print(f"Token 序列：{tokens}")
print(f"Token 数：{len(tokens)}")
```

**要点**：

| 要点 | 说明 |
|------|------|
| **首次联网** | 首次运行会下载词表并缓存，之后**完全离线** |
| **无需 API Key** | 纯本地库 |
| **速度极快** | Rust 实现，百万 token 级也在毫秒级 |
| **只对 OpenAI 模型准** | 拿它算 Qwen/DeepSeek 会偏 |

**⚠️ `encoding_for_model` 的坑**：

```python
# 错误做法：模型名不认识时直接抛异常
try:
    enc = tiktoken.encoding_for_model("some-new-model")
except KeyError:
    # 正确做法：回退到已知编码
    enc = tiktoken.get_encoding("o200k_base")
```

> 新模型发布后 tiktoken 未必同步更新，**必须加 fallback**。

**哪些模型对应哪个编码**（用 `get_encoding` 时）：

| 编码 | 用于 |
|------|------|
| `o200k_base` | GPT-4o 系列、较新的模型 |
| `cl100k_base` | GPT-4 / GPT-3.5-turbo 系列 |
| `p50k_base` | 更早的模型 |

### 5.3 方式三：transformers / AutoTokenizer（开源模型）

```python
import os

# 国内访问 HuggingFace 需配置镜像（可直连则删除此行）
os.environ["HF_ENDPOINT"] = "http://hf-mirror.com"

from transformers import AutoTokenizer

# 注意：这里应与目标模型一致
tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-V3")

text = "人工智能正在深刻改变我们的生活，从智能助手到自动驾驶，AI 无处不在。"

tokens = tokenizer.encode(text)
print(f"Token 序列：{tokens}")
print(f"Token 数：{len(tokens)}")
```

**要点**：

| 要点 | 说明 |
|------|------|
| **只下分词器** | 首次下载仅几 MB，**不含模型权重** |
| **完全离线** | 之后统计在本地进行 |
| **对开源模型最准** | 用的是模型**真正的**分词器 |
| **`encode` 默认加特殊 token** | 如需纯文本计数用 `encode(text, add_special_tokens=False)` |

> **你的笔记里有个小笔误**：注释写"以开源模型 Qwen3 为例"，代码用的是 `deepseek-ai/DeepSeek-V3`。**两者要一致**，否则算出来的 token 数就是错的——这正是这一节要强调的重点。

### 5.4 三种方式怎么选

| 场景 | 推荐 |
|------|------|
| **OpenAI 模型** | `tiktoken`（唯一选择） |
| **Anthropic 模型** | **官方 count_tokens**（最准） |
| **开源模型自部署** | `transformers` 对应 tokenizer |
| **国内闭源模型** | 优先用**服务商计数 API** |
| **需要极低延迟** | 本地库 + 缓存 |
| **需要绝对准确** | 服务商计数 API |

## 六、统一封装（生产建议）

```python
from abc import ABC, abstractmethod
import tiktoken
from functools import lru_cache


class TokenCounter(ABC):
    @abstractmethod
    def count(self, text: str) -> int: ...


class TiktokenCounter(TokenCounter):
    """OpenAI 系：本地、快、只对它自己准"""

    def __init__(self, model: str, fallback: str = "o200k_base"):
        try:
            self.enc = tiktoken.encoding_for_model(model)
        except KeyError:
            self.enc = tiktoken.get_encoding(fallback)

    def count(self, text: str) -> int:
        return len(self.enc.encode(text))


class HFTransformerCounter(TokenCounter):
    """开源模型：本地、慢一点、对目标模型最准"""

    def __init__(self, model_id: str):
        from transformers import AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(model_id)

    def count(self, text: str) -> int:
        return len(self.tok.encode(text, add_special_tokens=False))


class RemoteCounter(TokenCounter):
    """服务商计数 API：最准，但有网络开销与限流"""

    def __init__(self, fn):
        self._fn = fn

    def count(self, text: str) -> int:
        return self._fn(text)


@lru_cache(maxsize=8192)
def _cached(text: str, kind: str) -> int:
    """缓存：同一段文本反复统计是常态（重试、重放、对比）"""
    ...
```

### 6.1 三条工程原则

| 原则 | 理由 |
|------|------|
| **按模型选分词器** | 混用必然算错 |
| **必须缓存** | 同一文本会被统计多次（重试、预览、日志） |
| **必须有 fallback** | 新模型 / 网络失败时不能崩 |

## 七、Token 数到底由什么组成

很多人只算了"文本"，漏掉这些：

| 组成 | 是否计入输入 | 说明 |
|------|-------------|------|
| **正文文本** | ✅ | 你所想的那部分 |
| **消息格式开销** | ✅ | 每条消息有固定开销（role、分隔符），约 **3–4 token/条** |
| **系统提示** | ✅ | 常被忘记，但它**每轮都在** |
| **工具定义（schema）** | ✅ | **这是隐形大户**——20 个工具的 JSON Schema 轻松上万 token |
| **图片** | ✅ | 按分辨率折算，一张图可能上千 token |
| **PDF** | ✅ | 官方示例中一份 PDF ≈ 2188 token |
| **历史 thinking 块** | ⚠️ | Anthropic：**之前轮次的忽略**，当前轮计入 |
| **缓存命中部分** | ⚠️ | 计入 `input_tokens`，但**按折扣价计费** |
| **推理 token** | 输出侧 | 部分模型的 reasoning token 也计费 |

> **最容易被低估的是"工具定义"**。这也是为什么 MCP 接多了之后"什么都没干就花了很多钱"。

## 八、成本计算

### 8.1 基本公式

```
成本 = 输入 token × 输入单价 + 输出 token × 输出单价
```

**注意两点**：

1. **输入和输出单价不同**，输出通常贵 3–5 倍
2. **单位是"每百万 token"**（`/1M tokens`），不是"每千"

### 8.2 缓存带来的差异

| 类型 | 计价 |
|------|------|
| 首次写入缓存 | 通常**溢价**（比普通输入贵） |
| **命中缓存** | **大幅折扣**（常为 10% 甚至更低） |

**所以**：

> **同一份 system prompt + 工具定义反复发送时，命中缓存与否，成本可能差 10 倍。**
> 这也是"**保持前缀稳定**"这条工程约束的经济学根源。

### 8.3 一个算例

假设（单价为示意，**实际请查当前价目表**）：

- 输入 $3 / 1M tokens，输出 $15 / 1M tokens
- 一次请求：输入 50,000 token，输出 2,000 token

```
输入：50,000 / 1,000,000 × 3    = $0.15
输出： 2,000 / 1,000,000 × 15   = $0.03
合计                              = $0.18 / 次
```

**1 万次调用 = $1,800**。这就是为什么"事前拦截超长输入"值钱。

## 九、快速心算（无工具时）

| 内容类型 | 粗略估算 |
|----------|----------|
| 英文 | **字符数 ÷ 4** |
| 中文 | **字符数 ÷ 1.5**（约 0.6–0.7 token/字） |
| 代码 | **字符数 ÷ 3** |
| JSON | **字符数 ÷ 2.5**（标点太密） |

> ⚠️ 这些只用于**量级判断**。任何涉及**钱**或**硬限制**的地方，必须用真分词器。

## 十、常见坑（按危害排序）

| # | 坑 | 后果 | 解法 |
|---|----|------|------|
| **1** | **流式响应不算 token** | **账对不上，白送用户** | OpenAI 传 `stream_options={"include_usage": True}`；Anthropic 读 `message_delta` |
| **2** | **拿 tiktoken 算非 OpenAI 模型** | 偏差可达 30%+ | 按模型选分词器 |
| **3** | **忘了算工具定义** | 实际消耗远超预估 | 把 `tools` 一起计入 |
| **4** | **把事前估算当账单** | 财务对不上 | 计费一律用 `usage` |
| **5** | **`encoding_for_model` 未加 fallback** | 新模型直接崩 | `try/except KeyError` → `get_encoding` |
| **6** | **忘了系统提示** | 每轮都少算几千 token | 显式加进去 |
| **7** | **中文按英文比例算** | 成本低估近一倍 | 中文用 ÷1.5 |
| **8** | **tokenizer 与模型不一致** | 结果无意义 | 用模型**真正**的 tokenizer |
| **9** | **不缓存分词结果** | 重复计算浪费 CPU | `lru_cache` / Redis |
| **10** | **以为能预估输出长度** | 预算算不准 | 输出按上限设预算，不按均值 |

## 十一、生产架构建议

### 11.1 三层防线

```
┌─────────────────────────────────────────────┐
│ ① 入口层：本地估算（快，粗）                 │
│    超硬限制 → 直接拒，减少后续成本            │
├─────────────────────────────────────────────┤
│ ② 校验层：服务商计数 API（准，慢）            │
│    接近阈值时才调用，避免每次都打            │
├─────────────────────────────────────────────┤
│ ③ 结算层：响应 usage（精确，唯一可信）        │
│    写账单、写监控、做对账                     │
└─────────────────────────────────────────────┘
```

### 11.2 为什么分三层而不是一层

| 只做本地估算 | 只做服务商 API | **三层** |
|-------------|---------------|----------|
| 不准但快 | 准但每次都多一次网络往返 + 吃限流 | **快慢结合** |
| — | — | 精确对账靠 usage |

### 11.3 Tokenizer 服务化

当多个服务都要算 token 时：

```
Python 服务/库 → 内部 HTTP 微服务 → 各语言客户端调用
```

**收益**：避免"Java 服务用另一套分词器"导致的不一致。

### 11.4 监控指标

| 指标 | 用途 |
|------|------|
| `input_tokens` P50/P95/P99 | 发现异常长请求 |
| **缓存命中率** | 命中率低 = 前缀不稳定 = 多花钱 |
| **预估 vs 实际偏差** | 校准你的估算器 |
| **单用户 token 分布** | 发现滥用 |
| **工具定义占比** | 工具是否过多 |

## 十二、Checklist

**基础**
- [ ] 事前/事后两条链路都已实现
- [ ] 计费**只**用 `usage`，不用估算
- [ ] 流式响应已开启 usage 上报
- [ ] 分词器与目标模型**一一对应**

**事前**
- [ ] 超长输入在**调用前**拦截
- [ ] 额度不足在**调用前**提示
- [ ] 需要报价的场景已展示预估
- [ ] 模型路由基于预估 token
- [ ] 统计结果**有缓存**
- [ ] `encoding_for_model` 有 fallback

**完整计数**
- [ ] 系统提示计入
- [ ] **工具定义计入**
- [ ] 图片 / PDF 计入
- [ ] 消息格式开销计入

**成本**
- [ ] 缓存命中率有监控
- [ ] 前缀稳定性有保障
- [ ] 有单次请求成本上限
- [ ] 有用量告警

## 十三、总结

**Token 统计的本质是"两套数字，两个用途"：**

| | 事前 | 事后 |
|---|------|------|
| **本质** | 预算 | 账单 |
| **准度** | 估算 | 精确 |
| **价值** | **省下不该花的钱** | **知道自己花了多少** |
| **误用后果** | 当账单用 → 财务对不上 | 当事前用 → 防不住浪费 |

**五条最值得记住的原则**：

1. **计费只认 `usage`** —— 估算值可以用于决策，不能用于收钱
2. **分词器必须跟模型走** —— 混用不是"精度差一点"，是"算的是另一回事"
3. **工具定义是隐形大户** —— 只算文本会让你严重低估
4. **中文成本约为英文的 1.5–2 倍** —— 别用英文经验值套中文
5. **事前统计的价值在"拦截"，不在"精确"** —— 它的 KPI 是"少发了几次无效请求"

> **最后一句话**：
> **Token 数不是一个数字，而是三个不同的数字——你预估的、服务商算的、和账单上扣的。**
> 工程的任务是让这三者**尽量接近**，并永远**以第三个为准**。

---

> **资料说明**
> Anthropic count_tokens 的端点、参数、响应字段、免费/独立限流/不触发缓存/服务端工具只计首次采样/thinking 计数规则，依据**官方文档**（经镜像 `claude.yourdocs.dev` 读取，原文站因地区限制无法访问）。
> "1 token ≈ 4 字符，100 token ≈ 60–80 英文单词"与 `countTokens` 接口，依据 **Google Gemini / Firebase 官方文档**。
> `estimate-token-count` 接口、`kimi-k3` 示例。
> tiktoken、transformers 用法依据官方库文档；编码对应关系（`o200k_base` / `cl100k_base`）为公开已知事实。
>
> **需要核对的地方**：
> - **价格与限流数值**（$3/$15 每百万、Tier 1 = 100 RPM 等）**为示意或抓取时状态**，厂商调价频繁，**必须以当前价目表为准**。
> - **"约 3–4 token/条消息开销"** 是 OpenAI 长期公开的经验值，**随模型版本可能变化**，接入前建议实测。
> - **中文 ÷1.5 的估算比例**为经验值，实际依分词器差异较大，**仅用于量级判断**。
> - 你的笔记中 **注释写 Qwen3、代码用 DeepSeek-V3** 的不一致已在文中标出。
> - 所有引文为**中文意译**，非逐字直译。
