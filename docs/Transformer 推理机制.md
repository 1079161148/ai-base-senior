# Transformer 推理机制

transformer推理可视化：https://poloclub.github.io/transformer-explainer/

## 结论

推理（Inference）= 用**训练好、参数冻结**的模型，**自回归地逐个生成 token**：每次喂入已有序列，预测下一个 token，追加到序列末尾，再预测下一个，直到满足停止条件。与训练的最大区别是——**只做前向、不更新参数、串行生成**。

## 一、推理 vs 训练

| 维度 | 训练 | 推理 |
|------|------|------|
| 参数 | 每步更新 | **冻结不变** |
| 计算路径 | 前向 + 反向传播 | **仅前向** |
| 监督信号 | 有标签（下一个 token） | 无标签，**自己产出的 token 作为下一步输入** |
| 并行性 | 整段序列可并行算损失（teacher forcing） | 生成阶段**必须串行**，后一个依赖前一个 |
| 掩码 | 因果掩码防偷看 | 因果掩码照旧 |

## 二、自回归生成流程

```
prompt: "今天天气"
   │
   ▼
[前向] → 预测下一个 token = "真"
   │
   ▼
"今天天气真"
   │
   ▼
[前向] → 预测 = "好"
   │
   ▼
"今天天气真好" → ... 直到 EOS 或达到 max_tokens
```

每一轮都把**整个已生成序列**重新送入模型，模型输出最后一个位置的 logits → softmax → 采样。

## 三、两阶段：Prefill 与 Decode

| 阶段 | 做什么 | 计算特征 | 瓶颈 |
|------|--------|----------|------|
| **Prefill（预填充）** | 一次性**并行**处理整个 prompt，建立 KV Cache | 矩阵乘法多，**计算密集（compute-bound）** | GPU 算力 |
| **Decode（解码）** | 逐个 token 生成，每步只处理 1 个新 token | 主要读 KV Cache 与权重，**访存密集（memory-bound）** | 显存带宽 |

常用性能指标：

- **TTFT**（Time To First Token）：首 token 延迟 ≈ Prefill 耗时，影响"响应快不快"
- **TPOT / TPST**（Time Per Output Token）：每个后续 token 的平均耗时
- **Throughput（TPS）**：每秒生成 token 数，衡量总吞吐

> 长 prompt 慢在 Prefill；长回答慢在 Decode。

## 四、KV Cache（推理最关键优化）

### 为什么需要
Decode 时每生成一个新 token，注意力都要和**所有历史 token** 的 K、V 计算。若不缓存，每步都把历史重算一遍 → 总开销 \(O(n^2)\) 且大量重复。

### 做法
- 缓存每一层每个历史位置的 **K 和 V**（Q 只与当前新 token 有关，不需缓存）
- 新 token 只计算自己的 Q/K/V，注意力直接查历史缓存
- 单步相对增量成本从重算全序列降为 **只算新 token + 读缓存**

### 代价与变体
- **显存**：KV Cache 随序列长度**线性增长**，长上下文时显存是主要瓶颈
- 减小 KV Cache 的架构手段：
  - **MQA**（Multi-Query Attention）：所有头共享一份 K/V
  - **GQA**（Grouped-Query Attention）：分组共享，Llama 系列常用
  - **MLA**（Multi-head Latent Attention）：DeepSeek 用低秩压缩 K/V

## 五、采样策略（怎么从概率分布里选 token）

| 策略 | 说明 | 特点 |
|------|------|------|
| **Greedy** | 每步取概率最高的 token | 确定、可复现，但容易重复、缺多样性 |
| **Beam Search** | 同时保留 top-k 条候选路径，选整体得分最高 | 质量高，但慢、占显存 |
| **Temperature** | 用 \(T\) 缩放 logits 再 softmax | \(T<1\) 更确定、\(T→0\) 趋近贪心；\(T>1\) 更随机 |
| **Top-k** | 只保留概率最高的 k 个再采样 | 截断长尾，k 越大越多样 |
| **Top-p（nucleus）** | 取累积概率达到 p 的最小集合再采样 | 自适应候选数，常用默认策略 |
| **Repetition Penalty** | 降低已出现 token 的概率 | 缓解复读机现象 |

## 六、停止条件

- 生成 **EOS**（结束符）token
- 达到 **max_tokens** 上限（硬截断，可能句子不完整）
- 命中 **stop sequences**（指定字符串）

## 七、常见推理优化技术

| 技术 | 作用 |
|------|------|
| **KV Cache** | 避免重复计算历史 K/V（必开） |
| **Continuous Batching** | 动态把不同请求拼进同一 batch，提升 GPU 利用率（vLLM 的 PagedAttention） |
| **量化** | FP16 → FP8/INT8/INT4，降显存、提吞吐，略有精度损失 |
| **FlashAttention** | 优化注意力计算的分块与显存访问 |
| **投机解码（Speculative Decoding）** | 小模型先草拟多个 token，大模型一次并行校验，加速生成 |
| **并行策略** | Tensor Parallel / Pipeline Parallel 支撑超大模型多卡推理 |

## 八、与训练流程的衔接

训练学到的是"**给定前文预测下一个 token**"这一能力；推理就是把该能力**反复调用**：

```
文本 → 分词得 ID → Embedding → Transformer Block × N → 线性层 → logits
                                                          │
                                              采样出下一个 token
                                                          │
                                        追加回序列 → 循环
```

一次训练，无数次的"预测 - 采样 - 追加"就是推理的全部。
