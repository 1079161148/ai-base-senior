# HITL 与持久化执行

> **权威依据**
> ① **Temporal**《The Definitive Guide to Durable Execution》（Tom Wheeler，2025-05-06）
> ② **LangGraph** Human-in-the-loop / Checkpointer 机制
> ③ **Anthropic**《How we built our multi-agent research system》— durable execution 实践
> ④ 本知识库：`Graph Engineering.md`、`Agent安全与护栏.md`、`Agent规划与任务分解.md`

## 结论

**这两件事不是并列关系，而是依赖关系：**

> **持久化执行是 HITL 的前提。**
> **没有持久化，"暂停"就没有意义**——进程一结束状态就没了，人批了也接不上。

| | 持久化执行 | HITL（人类介入） |
|---|---|---|
| **解决什么** | 崩溃、长时间等待、状态丢失 | 高后果动作需要人决策 |
| **本质** | **让执行可恢复** | **让执行可暂停** |
| **关系** | **地基** | **上层建筑** |

**Temporal 的官方定义（一句话）**：

> **"Durable Execution is crash-proof execution."**
> **持久化执行就是"崩溃安全"的执行。**

**关键澄清**：它**不承诺不发生崩溃**，而是承诺**崩溃不产生后果**。

> 好比**戴防水手表不能防止你掉进泳池，但能保证表还在走**。

## 一、为什么 Agent 必须能"暂停"

### 1.1 三个真实场景

| 场景 | 需要暂停多久 |
|------|-------------|
| **高危动作审批**（发邮件、转账、部署） | 几分钟到几小时 |
| **人工补充信息**（缺一个参数、需要选择方案） | 几分钟到几天 |
| **外部长任务**（等待用户上传、等待第三方回调） | 几小时到几个月 |

### 1.2 传统做法的三个痛点

| 做法 | 问题 |
|------|------|
| **同步阻塞等** | 进程不能挂着好几小时，连接会断、服务会重启 |
| **发通知+人工重跑** | 前面的步骤全部重做，成本翻倍 |
| **自建状态表** | 要写大量"把变量存库、再取出来"的胶水代码 |

> **Temporal 引用的一个观察**（Cristian《Reliable Computer Systems》）：
> **失败处理代码常常占生产系统全部代码的三分之二以上**——远多于"快乐路径"的代码。

## 二、持久化执行的四个核心特性

> Temporal 官方给出，**适用于所有持久化执行平台**。

### 2.1 特性一：虚拟化执行（Virtualizes Execution）

| 普通执行 | 持久化执行 |
|----------|-----------|
| 在**一个进程**里跑完 | 可跨越**一系列进程**，甚至不同机器 |
| 进程崩溃 → 变量全丢、不知道跑到哪 | **透明地在新区进程恢复**，状态重建，像没崩过一样 |

**Temporal 的例子**：五个步骤 A→B→C→D→E
- 完成 A、B 后崩在 C → 无持久化：**彻底结束**
- 有持久化：在**新进程**恢复，A、B 的结果还在 → C 完成 → 又崩在 D → **再换一台机器**恢复 → 完成

> **从开发者视角看，这就是一次普通执行。**

### 2.2 特性二：不受时间限制

> **"持久化执行让应用可以运行到达到目标为止。"**

| 普通程序 | 持久化执行 |
|---|---|
| 今天启动的程序，不能指望六个月后还在跑 | **一个 `for` 循环 + `sleep` 就能实现跨月通知** |

**官方示例（伪代码）**：

```
function Notifier(String username) {
    for interval in [1, 7, 30, 60, 90, 180] {
        sleep(Time.days(interval))
        sendNotification(username)
    }
}
```

> **这意味着**：单次 API 调用可以等几秒，**也可以等几个月**。

### 2.3 特性三：自动保存应用状态

> **不需要为了防崩溃而专门建一个应用数据库。**

| 做法 | 代价 |
|------|------|
| 自建状态表 | 写大量"存→取→还原"的代码，而存库**根本不是业务需求** |
| **持久化执行** | **包括局部变量在内的所有变量都持久** |

> **注意**：**你仍然可能需要数据库**——为了报表、查询、审计。但**不是为了防崩溃**。

### 2.4 特性四：与硬件无关

| 硬件容错 | 持久化执行 |
|----------|-----------|
| 昂贵机器（热插拔 CPU/内存） | **普通 VM / 容器** |
| 无法防软件缺陷（除零、kernel panic） | **软件层可靠性，能防** |
| 受物理位置与专有网络限制 | **本地与云皆可** |

## 三、Agent 为什么比普通后台任务更需要它

| Agent 特性 | 为什么普通任务处理不了 |
|-----------|----------------------|
| **运行时间长**（小时级到天级） | 不能同步等，进程会被回收 |
| **外部副作用不可重复** | 发两次邮件、扣两次款 = 事故 |
| **步骤间有强状态依赖** | 重启即丢失中间推理结果 |
| **需要人等** | 审批可能几小时，不能让连接挂着 |
| **LLM 调用贵** | 重跑全流程 = 重复花钱 |

> **Anthropic 的实践总结**：Agent 长时间运行、跨多次工具调用维持状态，**需要 durable execution**——不能出错就从头重启（代价高、体验差），需支持**从出错点恢复**，配合**确定性重试 + 定期 checkpoint**。

### 3.1 一个成本对比

```
任务：8 步，每步一次 LLM 调用（约 $0.05），第 7 步失败

无持久化：  重跑第 1–7 步 = 多花 $0.35 + 用户多等 3 分钟
有持久化：  从第 7 步重跑   = 多花 $0.05 + 用户多等 5 秒
```

> **失败率越高、任务越长，差距越大。**

## 四、五个核心概念

| 概念 | 含义 | 类比 |
|------|------|------|
| **Checkpoint（检查点）** | 某一时刻的完整状态快照 | 游戏存档 |
| **Thread（线程）** | 一条独立的执行时间线 | 一个存档槽 |
| **`thread_id`** | 时间线的唯一标识 | 存档槽编号 |
| **`checkpoint_id`** | 时间线上的某一刻 | 第 N 个存档 |
| **Resume（恢复）** | 从某个检查点继续 | 读档 |

### 4.1 两个坐标决定一切

```
thread_id     →  "哪条时间线"
checkpoint_id →  "时间线上的哪一刻"
```

**HITL 恢复、时间旅行、分叉，全都靠这两个坐标定位。**

### 4.2 Checkpoint 里到底存了什么

| 内容 | 说明 |
|------|------|
| **状态字段值** | 你的业务状态 |
| **`checkpoint_id` / `parent_checkpoint_id`** | 形成时间线/分叉 |
| **下一步待执行节点** | 恢复时知道往哪走 |
| **pending writes** | 中断信息就存在这里 |

### 4.3 持久化粒度（重要权衡）

| 模式 | 说明 | 代价 |
|------|------|------|
| **只在结束时写** | 最省 | **崩了就全丢** |
| **异步写（默认折中）** | 后台批量落盘 | 极端情况下丢最后几步 |
| **每步同步写** | 最安全 | 最慢 |

> **HITL 场景必须能在中断点落盘** → 选**异步或同步**，不能选"只在结束时写"。

## 五、HITL 的四种模式

| # | 模式 | 触发点 | 人做什么 |
|---|------|--------|----------|
| **1** | **Approve / Reject** | 关键动作前（发邮件、写库） | 批 / 拒 |
| **2** | **Edit（编辑状态）** | 任意检查点 | 直接改状态字段 |
| **3** | **Review Tool Calls** | 工具节点之前 | 改参数、改工具、或拒绝 |
| **4** | **Clarify（澄清）** | 信息不足时 | 补充信息 / 选择方案 |

### 5.1 模式 1：Approve / Reject

```
Agent 准备执行 send_email
        ↓
interrupt({"action": "send_email", "to": "...", "body": "..."})
        ↓
人看到完整信息 → 批准 / 拒绝
        ↓
批准 → 执行
拒绝 → 把拒绝原因作为 ToolMessage 回灌给模型，让它重新决策
```

> **关键设计**：**拒绝不是"终止"，而是"给了模型新信息"**——它应该能换个方案再来。

### 5.2 模式 2：Edit

> 直接修改状态里的字段，**从新检查点继续**。

**适合**：模型提取有误（少提了一个风险条款）、计划需要微调。

### 5.3 模式 3：Review Tool Calls

> 在工具节点前插入一个人审节点，**审阅模型生成的 tool calls**，可改参数、改工具名、或拒绝。

**为什么这条重要**：**工具参数错误是最常见的 Agent 事故来源**（路径越界、SQL 危险、URL 外发）。

### 5.4 模式 4：Clarify

> 信息不足时不硬猜，暂停问人。

> **反模式**：让模型"合理推断"缺失参数 → 猜错后下游全错。

## 六、中断的实现（以 LangGraph 为例）

### 6.1 基本形状

```python
from langgraph.types import interrupt, Command

def review_node(state):
    decision = interrupt({
        "question": "是否批准该操作？",
        "payload": state["pending_action"],
    })
    # decision 就是恢复时传入的值
    return {"approved": decision["approved"]}
```

```python
# 第一次调用：会停在 interrupt 处
result = graph.invoke({"messages": [...]}, config)
print(result["__interrupt__"])

# 人工给出决策后恢复
result = graph.invoke(Command(resume={"approved": True}), config)
```

### 6.2 ⚠️ 最危险的陷阱：恢复时节点会从头重跑

> **`interrupt()` 是"抛出"而非"返回"。**
> **恢复时，该节点会从第一行重新执行**，这一次 `interrupt()` 直接返回 `Command(resume=...)` 的值。

**含义**：

```python
def review_node(state):
    send_email(state["to"], state["body"])     # ⚠️ 恢复时会执行两次！
    decision = interrupt({"..."})
    return {"approved": decision["approved"]}
```

**邮件发了两封。** 这不是框架 bug，是**重放模型的固有约束**。

### 6.3 正确写法

```python
def review_node(state):
    # ✅ 只做纯计算，无副作用
    payload = {"action": "send_email", "to": state["to"], "body": state["body"]}

    decision = interrupt({"question": "批准？", "payload": payload})

    # ✅ 副作用放在 interrupt 之后，且带幂等键
    if decision["approved"]:
        send_email_idempotent(
            to=state["to"],
            body=state["body"],
            idempotency_key=f"{state['run_id']}:send_email",
        )
    return {"approved": decision["approved"]}
```

### 6.4 三条硬规则

| 规则 | 理由 |
|------|------|
| **① `interrupt()` 之前不要有副作用** | 会执行两次 |
| **② `interrupt()` 不能在 `try/except` 里** | 会被吞掉，中断失效 |
| **③ 副作用必须幂等** | 重放是常态，不是异常 |

## 七、确定性约束（最容易被忽略的一层）

### 7.1 重放模型

> **持久化执行恢复的方式是"重放事件历史"**——不是"从内存快照恢复"，而是**从头把确定性代码再跑一遍**，把不确定的结果替换成历史记录。

```
原始执行：  step1 → 记录"得到 X" → step2(用到 X) → ...
崩溃恢复：  step1 重跑 → 不真的执行，直接返回记录的 X → step2 → ...
```

**所以**：**step1 必须是确定性的**，否则重跑会得到不同的 X。

### 7.2 什么代码不能放在工作流里

| 反模式 | 为什么 | 正确做法 |
|--------|--------|----------|
| `time.time()` / `datetime.now()` | 重跑时间不同 | 用框架提供的时间 API |
| `random.random()` / `uuid4()` | 重跑值不同 | 用框架的确定性随机 |
| **直接发 HTTP 请求** | 重跑会重复请求 | 包成"活动/Activity"，其结果被记录 |
| `os.environ` 读取易变配置 | 重跑环境不同 | 启动时读取并固定 |
| **字典遍历顺序依赖** | 语言/版本差异 | 显式排序 |

> **一句话**：**工作流里只写"做什么"，把"和外部世界打交道"都包成被记录的活动。**

### 7.3 对 Agent 的含义

| Agent 组件 | 归类 |
|-----------|------|
| 计划生成（LLM 调用） | **活动**（结果要记录） |
| 工具调用 | **活动** |
| 检索 | **活动** |
| 路由判断（纯函数） | 工作流 |
| 状态转移（纯函数） | 工作流 |

> **LLM 调用本身是非确定性的**——所以必须**被记录**，重放时**直接读结果**，不再真的调模型（这也顺便省了钱）。

## 八、幂等：持久化执行的孪生要求

### 8.1 为什么必须

```
恢复 → 节点重跑 → 副作用执行第二次
```

**不是"可能发生"，是"设计上就会发生"。**

### 8.2 三种实现方式

#### 方式一：幂等键（最通用）

```python
def send_email_idempotent(to: str, body: str, idempotency_key: str):
    # ① 尝试抢占
    claimed = db.execute(
        "INSERT INTO actions (idem_key, status) VALUES (?, 'in_progress') "
        "ON CONFLICT (idem_key) DO NOTHING",
        (idempotency_key,),
    )
    if claimed.rowcount == 0:
        # ② 已经执行过 → 直接返回上次结果
        return db.query("SELECT result FROM actions WHERE idem_key = ?", (idempotency_key,))

    result = do_send(to, body)

    db.execute("UPDATE actions SET status='done', result=? WHERE idem_key=?", (result, idempotency_key))
    return result
```

#### 方式二：状态机检查

```python
def approve_and_send(state):
    if state["status"] != "approved":
        return state                      # 已经做过了
    state["status"] = "sending"
    result = send_email(state)
    state["status"] = "sent"
    return state
```

#### 方式三：交给外部系统

> 很多外部 API 本身支持幂等键（如支付网关的 `Idempotency-Key` 请求头）。**优先用它。**

### 8.3 幂等键怎么设计

| 要素 | 说明 |
|------|------|
| **运行 ID** | 同一次任务 |
| **动作标识** | 哪个动作（`send_email` / `charge`） |
| **目标对象** | 对谁（用户 ID / 订单号） |

```python
idem_key = f"{run_id}:{action}:{target_id}"
```

> **❌ 不要用**：时间戳、随机数、`uuid4()`——**每次重跑都不一样，等于没有幂等**。

## 九、完整实现示例

```python
from dataclasses import dataclass, field
from enum import Enum
import json


class State(str, Enum):
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class RunState:
    run_id: str
    status: State = State.PLANNING
    plan: list[dict] = field(default_factory=list)
    step_index: int = 0
    pending_action: dict | None = None
    executed_actions: list[str] = field(default_factory=list)   # 幂等记录
    interrupt_payload: dict | None = None


def agent_loop(state: RunState, store) -> RunState:
    while state.status in (State.RUNNING, State.EXECUTING):

        if state.step_index >= len(state.plan):
            state.status = State.DONE
            break

        step = state.plan[state.step_index]
        tool = get_tool(step["tool"])

        # ---- 高危动作 → 停下来等人 ----
        if tool["risk"] >= 3:
            state.status = State.AWAITING_APPROVAL
            state.pending_action = {"step": step, "tool": step["tool"], "args": step["args"]}
            state.interrupt_payload = {
                "question": f"即将执行不可逆操作：{step['tool']}",
                "args": step["args"],
                "reason": step.get("reason", ""),
                "risk": "不可逆",
            }
            store.save(state)          # ← 关键：落盘
            return state               # ← 交给调用方（人）

        # ---- 普通动作 → 直接执行 ----
        execute_step(state, step)
        state.step_index += 1
        store.save(state)

    return state


def resume_with_decision(state: RunState, approved: bool, store) -> RunState:
    """人审批后恢复"""
    action = state.pending_action

    if not approved:
        # 拒绝 → 把原因回灌，让模型重新规划
        state.plan = replan_after_rejection(state, reason="人工拒绝")
        state.status = State.RUNNING
        state.pending_action = None
        store.save(state)
        return state

    # 批准 → 幂等执行
    idem = f"{state.run_id}:{action['tool']}:{action['step'].get('target','-')}"
    if idem not in state.executed_actions:
        execute_step(state, action["step"], idempotency_key=idem)
        state.executed_actions.append(idem)

    state.step_index += 1
    state.pending_action = None
    state.status = State.RUNNING
    store.save(state)

    return agent_loop(state, store)     # 继续往下跑
```

### 9.1 这段代码的四个要点

| 要点 | 代码位置 |
|------|----------|
| **状态落盘再返回** | `store.save(state)` 在 `return` 前 |
| **幂等记录** | `state.executed_actions` + `idempotency_key` |
| **拒绝 ≠ 终止** | 拒绝后 `replan_after_rejection` |
| **暂停信息完整** | `interrupt_payload` 带 args / reason / risk |

## 十、审批节点该给审批人看什么

> **设计原则**：**审批人要在 10 秒内做出判断。**

| 必给 | 为什么 |
|------|--------|
| **拟执行的具体动作** | 不是"要发送邮件"，而是**完整草稿** |
| **参数** | 收件人、金额、目标环境 |
| **支撑证据** | 为什么做这个动作（引用了哪条数据） |
| **风险等级** | 一级 / 不可逆 / 涉及资金 |
| **影响范围** | 一个用户 / 全部用户 |
| **超时与默认行为** | 30 分钟无人处理怎么办 |

### 10.1 超时策略（必须显式定义）

| 策略 | 适用 |
|------|------|
| **超时即拒绝**（安全默认） | 高危、不可逆 |
| **超时即批准** | ❌ **绝不推荐** |
| **超时升级** | 转给上级 / 值班 |
| **超时不处理，挂着** | 内部工具、无时效要求 |

> **默认应该是"超时即拒绝"**——安全失败优于不安全成功。

### 10.2 拒绝的处理

> **拒绝不是终点，是新的输入。**

```
拒绝理由："这个收件人不对，应该发给财务部而不是 HR"
        ↓
回灌给模型 → 重新规划 → 再次提交审批
```

## 十一、时间旅行与分叉

| 能力 | 用途 |
|------|------|
| **回放** | 从某个历史检查点重跑后续步骤（**注意：外部副作用会再次发生**） |
| **分叉** | 从历史某点修改状态，产生新分支，原分支保留 |
| **查看历史** | 调试"它为什么这么走" |

> **用途**：调试、纠错后重跑、A/B 不同决策路径。

> **⚠️ 回放的副作用风险**：重跑会**真的再发一次邮件**。所以回放必须在**隔离环境**或**幂等保护**下进行。

## 十二、技术选型

| 方案 | 适合 | 代价 |
|------|------|------|
| **自建（状态表 + 定时任务）** | 极简场景、步数少 | 要自己写恢复、重试、幂等 |
| **Agent 框架内置**（LangGraph checkpointer 等） | Agent 专用、图结构 | 只能用于该框架，通用性差 |
| **工作流引擎**（Temporal 等） | 需要跨系统、跨月、强可靠 | 学习成本高、确定性约束严 |
| **云厂商 Durable Functions** | 已在云上 | 绑定厂商 |

### 12.1 选型三个问题

| 问题 | 指向 |
|------|------|
| 任务会**跑几天以上**吗？ | 是 → 工作流引擎 |
| 需要**跨系统协调**（多服务）吗？ | 是 → 工作流引擎 |
| 只是**单个 Agent 内部**暂停吗？ | 是 → 框架内置即可 |

> **务实建议**：**先用 Agent 框架的 checkpointer**（大多已够用），撞到"跨系统"或"跨月"再上工作流引擎。

## 十三、常见坑

| # | 坑 | 后果 | 解药 |
|---|----|------|------|
| **1** | **`interrupt()` 前有副作用** | **恢复时执行两次**（发两封邮件） | 副作用移到 interrupt 后 |
| **2** | **副作用不幂等** | 重放即重复 | 幂等键 |
| **3** | **状态没落盘就返回** | 人批了也接不上 | 返回前 `save()` |
| **4** | **用时间戳/随机数做幂等键** | 每次重跑都不同 = 没幂等 | 用 `run_id:action:target` |
| **5** | **工作流里直接发 HTTP** | 重放重复请求 | 包成活动/Activity |
| **6** | **`interrupt()` 放在 try/except 里** | 中断被吞 | 不要在异常捕获范围内 |
| **7** | **审批信息不含参数** | 人只能盲批 | 给完整草稿 + 证据 |
| **8** | **超时策略默认批准** | 无人值守时自动放行高危动作 | 默认拒绝 |
| **9** | **`thread_id` 复用** | 不同任务串线 | 一任务一线程 |
| **10** | **只在结束时持久化** | 崩了全丢 | 每步或每 superstep 落盘 |
| **11** | **回放到生产环境** | 重复执行副作用 | 隔离环境 + 幂等 |
| **12** | **拒绝后直接终止** | 丢失了一次好机会 | 拒绝理由回灌、重规划 |

## 十四、Checklist

**基础设施**
- [ ] 有 Checkpointer / 状态存储（**生产不用内存实现**）
- [ ] 有 `thread_id` 隔离（一任务一线程）
- [ ] 持久化粒度是"每步"而非"结束时"
- [ ] 有 `get_state` / `get_state_history` 等可观测接口

**HITL**
- [ ] 高危动作（L3/L4）都会暂停
- [ ] 审批信息含：完整参数、证据、风险等级、影响范围
- [ ] **超时策略显式定义**（默认拒绝）
- [ ] 拒绝理由会回灌给模型重规划
- [ ] `interrupt()` 前**没有任何副作用**
- [ ] `interrupt()` 不在 try/except 内

**幂等**
- [ ] 所有外部副作用都有**幂等键**
- [ ] 幂等键由 `run_id + action + target` 构成
- [ ] **未**使用时间戳/随机数做键
- [ ] 有"已执行动作"记录

**确定性**
- [ ] 工作流里没有 `now()` / `random()` / `uuid4()`
- [ ] 所有外部调用都包成活动（结果被记录）
- [ ] LLM 调用结果会被记录（重放不再花钱）

**运维**
- [ ] 能查看某个 run 的完整历史
- [ ] 能手动恢复 / 干预
- [ ] 回放只在隔离环境进行

## 十五、总结

**两件事的关系：**

```
持久化执行（地基）
    ├─ 崩溃可恢复
    ├─ 长时间可等
    ├─ 状态自动保存
    └─ 在此基础上 → HITL（暂停/审批/恢复）
```

**五条最值得记住的原则**：

1. **没有持久化就没有 HITL** —— 顺序不能颠倒
2. **恢复 = 重放** —— 所以 `interrupt()` 之前的代码**会执行两次**
3. **幂等不是优化，是前提** —— 不幂等的副作用在重放模型下必然重复
4. **工作流只写"做什么"，外部交互包成活动**
5. **审批的默认应该是拒绝** —— 安全失败优于不安全成功

> **最后一句话**：
> **Agent 从"能跑通"到"敢上线"的分水岭，不是模型多强，而是——**
> **它崩了能不能接着跑，它想干坏事时能不能停下来问一句。**

---

> **资料说明**
> 持久化执行的定义（"crash-proof execution"）、四个关键特性（虚拟化执行、不受时间限制、自动保存状态、硬件无关）、防水手表比喻、五步骤崩溃恢复示例、`Notifier` 伪代码、"失败处理代码占 2/3"的引用，**依据 Temporal《The Definitive Guide to Durable Execution》（Tom Wheeler，2025-05-06）原文**。
> Agent 需要 durable execution、断点恢复、确定性重试 + checkpoint，**依据 Anthropic 多 Agent 研究系统原文**。
> "持久暂停 + 从该状态恢复 + 携带证据与风险标记"的审批节点要求，依据 **V12 Labs 对 Graph Engineering 的实践总结**。
> LangGraph 的 `interrupt` / `Command(resume)` / checkpointer / `thread_id` / 时间旅行机制，**依据对该框架的既有理解**。
>
> **重要限制**：
> - ⚠️ **LangGraph 文档页发生重定向，正文未抓取成功**，第六章的 API 名称、`__interrupt__` 字段、`durability` 参数等**未经原文核对**，且**随版本变化**（`state.interrupts` 等新 API 已出现）。接入前请查当前文档。
> - Temporal 的四个特性是**该公司的定义**，其他持久化执行平台可能表述不同。
> - **第七章"重放事件历史"是对持久化执行通用模型的描述**，Temporal 原文未在这一篇中展开重放与确定性约束的细节。
> - 第九章代码为**示意**：`store` / `execute_step` / `replan_after_rejection` / `db` 未实现，**不能直接运行**。
> - 第十章审批信息项为**产品设计经验归纳**，非官方标准。
> - 所有引文为**中文意译**，非逐字直译。
