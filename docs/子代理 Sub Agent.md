# 子代理 Sub Agent

> **权威依据**
> ① **Claude Code 官方文档**《Create custom subagents》（docs.claude.com/en/docs/claude-code/sub-agents）— 实现规范
> ② **Anthropic**《How we built our multi-agent research system》— 架构范式
> ③ **Cognition**《Don't Build Multi-Agents》— 反方约束
> ④ **Addy Osmani**《Loop Engineering》— maker/checker 设计

## 结论

**子代理是"在独立上下文窗口中运行、拥有自己的 system prompt 与工具权限、只把结论带回主对话"的专用助手。**

> **官方定义**：*"Subagents 是处理特定类型任务的专用 AI 助手。"*
>
> 四要素：**独立上下文窗口** + **自定义 system prompt** + **特定工具访问权限** + **独立权限设置**。

一句话记住：**子代理的本质不是"多一个 AI"，而是"多一个垃圾桶"——把不需要留在主对话里的东西（搜索记录、日志、文件内容）倒进去，只把结论捡回来。**

## 一、它到底解决什么问题

### 1.1 一句话动机

> **当某个附带任务会把大量搜索结果、日志或文件内容灌进主对话，而你之后不会再引用这些内容时——让子代理在自己的上下文里做完，只返回摘要。**

### 1.2 五个官方列出的作用

| 作用 | 说明 |
|------|------|
| **保留上下文** | 把探索与实现过程挡在主对话之外 |
| **强制约束** | 限制子代理可用的工具 |
| **复用配置** | 用户级子代理可跨项目使用 |
| **专精行为** | 针对特定领域编写聚焦的 system prompt |
| **控制成本** | 把任务路由到更快、更便宜的模型（如 Haiku） |

### 1.3 与四个相邻概念的区别（很容易混淆）

| 概念 | 说明 |
|------|------|
| **Subagents** | 在**单个会话内**工作 |
| **background agents** | 多个独立会话并行运行，集中监控 |
| **cross-session messaging** | 会话之间互相传递消息 |
| **agent teams** | Claude 生成并监督的协作会话团队 |

## 二、核心机制：上下文隔离（理解一切的钥匙）

### 2.1 启动时会加载什么

子代理**不是**主对话的副本。它启动时只有六样东西：

| # | 加载内容 | 说明 |
|---|----------|------|
| 1 | **自己的 system prompt** | 代理自己的 prompt + Claude Code 追加的环境细节 |
| 2 | **任务消息** | 主对话委派时撰写的任务摘要 |
| 3 | **CLAUDE.md 各层级** | `~/.claude/CLAUDE.md`、项目规则、`CLAUDE.local.md`、托管策略文件、`AGENTS.md` |
| 4 | **Git status** | 仓库快照（独立 worktree 中则显示该 worktree 的分支/状态/近期提交） |
| 5 | **预加载技能** | `skills` 字段所列技能的**完整内容** |
| 6 | **同级代理名册** | 列出 `main` 及其他具名代理（是启动时的**快照**） |

> **关键否定**：它**不包含 Claude Code 自身的 system prompt**。

### 2.2 明确不会传递的状态

| 不传递 | 后果 |
|--------|------|
| **输出风格** | 子代理运行自己的 system prompt，输出风格不生效（fork 除外） |
| **自动记忆（auto memory）** | 需用 `memory` 字段给子代理**自己的**持久记忆 |
| **上下文窗口大小** | 由子代理**自己的模型**决定，不是父级的 |

> **这是最容易踩的坑**：把小窗口模型配给子代理，它就只有小窗口——**委派给 haiku 做重活会直接失败**。

### 2.3 输出扫描（安全机制）

Claude Code 在主对话读取子代理报告前会扫描：

| 机制 | 做法 |
|------|------|
| **插入反斜杠** | 对模仿 Claude Code 自身输出的文本（如 `<system-reminder>` 标签、`Human:`/`Assistant:` 开头的行）插反斜杠，使其变普通文本 |
| **标记行** | 报告模仿标签或提及 `bypassPermissions` 等权限设置时，前置 `[harness: subagent output matched instruction-shaped pattern(s):` 标记 |

**扫描的边界（重要）**：

> 扫描**不改写、不删除**内容，也**不判断是否恶意**。
> 它**不能替代**对子代理可达范围的限制。

**为什么需要这个**：子代理读取的是**外部内容**（网页、issue、日志），这些内容可能包含**针对 Agent 的注入指令**。扫描是**间接提示注入**的最后一道软防线。

## 三、配置文件格式

子代理是**带 YAML frontmatter 的 Markdown 文件**。`---` 之间是配置，其后的正文即 **system prompt**。

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---
You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
```

**两条硬规则**：

1. **仅 `name` 和 `description` 为必填**
2. 多词字段名用 **camelCase**（`maxTurns`、`disallowedTools`），**无法识别的字段会被静默忽略**——写错一个字母不会报错，只会不生效

### 3.1 完整字段表（19 个）

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | 唯一标识，≤256 字符；不能含 `:`；不能以 `-` 开头。Hooks 以此值作 `agent_type`。**文件名无需匹配** |
| `description` | ✅ | **Claude 何时应委派给此子代理**（决定是否被调用） |
| `tools` | ❌ | 允许的工具，逗号分隔或 YAML 列表；省略则继承全部。支持 `mcp__github__*` 等服务器级条目 |
| `disallowedTools` | ❌ | 拒绝的工具，从池中移除。⚠️ 带限定符（如 `Bash(git push *)`）会**移除整个 Bash 工具** |
| `model` | ❌ | `sonnet` / `opus` / `haiku` / `fable` / 完整模型 ID / `inherit` |
| `permissionMode` | ❌ | `default`(`manual`) / `acceptEdits` / `auto` / `dontAsk` / `bypassPermissions` / `plan` |
| `maxTurns` | ❌ | 最大 agentic 轮数；达上限标记「部分完成」，可恢复续跑 |
| `autoCompactWindow` | ❌ | 单独下调压缩窗口，`100000`–`1000000`。**必须写纯整数**（`200k` 会被读成 200 而失效） |
| `skills` | ❌ | 启动时**注入完整技能内容**（非仅描述），最多前 32 个 |
| `mcpServers` | ❌ | 该子代理可用的 MCP 服务器：引用已配置的，或**内联完整定义** |
| `hooks` | ❌ | 仅该子代理生命周期内生效的 hooks |
| `memory` | ❌ | 持久记忆作用域：`user` / `project` / `local` |
| `background` | ❌ | `true` 则即使 Claude 请求等待也保持后台运行 |
| `omitClaudeMd` | ❌ | `true` 则不加载 CLAUDE.md（托管策略文件仍加载） |
| `effort` | ❌ | `low` / `medium` / `high` / `xhigh` / `max`（依模型而定） |
| `isolation` | ❌ | `worktree`：在临时 git worktree 中运行，获得仓库隔离副本 |
| `color` | ❌ | 界面显示颜色 |
| `initialPrompt` | ❌ | 作为主会话代理（`--agent`）时的首个用户轮次内容 |
| `experimental` | ❌ | 实验选项；`cacheTtl: 5m` 或 `1h` 控制提示缓存生命周期 |

### 3.2 文件会被静默跳过的五种情形

| 情形 | 结果 |
|------|------|
| 无 `name` | 视为同目录的说明文档 |
| 开头 `---` 不是第一行 | 视为无 frontmatter |
| `name` 以 `-` 开头 / 含 `:` / 超过 256 字符 | 跳过并写 debug 日志 |
| 有 `name` 但无 `description` | 跳过 |
| YAML 无法解析 | 跳过 |

**排查方法**：

```bash
claude --debug                                    # 搜索 does not recognize or apply
claude plugin validate .claude/agents             # 预检
```

> 日志里搜 `does not recognize or apply`（拼错的字段）或 `invalid autoCompactWindow`（值格式错）。

## 四、目录位置与优先级

| 位置 | 作用域 | 优先级 |
|------|--------|--------|
| **Managed settings** | 组织级 | **1（最高）** |
| `--agents` CLI 标志 | 当前会话 | 2 |
| `.claude/agents/` | 当前项目 | 3 |
| `~/.claude/agents/` | 所有项目 | 4 |
| 插件 `agents/` 目录 | 插件启用处 | 5（最低） |

### 4.1 项目级的两条扫描规则

- 从**当前工作目录向上走到仓库根**，逐层扫描 `.claude/agents/`
- 同名时 **离工作目录最近的优先**

### 4.2 递归与命名的差异（易踩坑）

| 场景 | 行为 |
|------|------|
| 项目/用户级子目录 | 子目录路径**不影响身份**，身份仅来自 `name` 字段 |
| 同一树内重名 | 按文件系统读取顺序加载其一（**无文档化优先级**），`/doctor` 会报告 |
| **插件**子目录 | `my-plugin/agents/review/security.md` → `my-plugin:review:security`，**子目录成为作用域标识** |

### 4.3 热加载

Claude Code 监视 `~/.claude/agents/` 与 `.claude/agents/`，**几秒内生效**，无需重启。

**仍需重启的三种情况**：

1. 在**新建**的 `agents` 目录中创建首个文件（监视器只覆盖启动时已存在的目录）
2. 通过 `--add-dir` / `/add-dir` 添加的目录（不被监视）
3. 使用 `--disable-slash-commands` 启动的会话

## 五、内置子代理

| 名称 | 模型 | 工具 | 用途 |
|------|------|------|------|
| **Explore** | 主对话模型 | **只读**（Write/Edit 被拒） | 文件发现、代码搜索、代码库探索 |
| **Plan** | 继承主对话 | **只读** | plan 模式下的代码库调研 |
| **General-purpose** | 见解析顺序 | 全部 | 复杂调研、多步操作、代码修改 |
| **claude** | 无自有模型 | 全部 | 兜底；后台会话的默认代理 |
| **statusline-setup** | Sonnet | — | 运行 `/statusline` 时 |
| **claude-code-guide** | Haiku | — | 询问 Claude Code 功能时 |

### 5.1 Explore 的彻底程度分级（值得借鉴的设计）

Claude 委派时会指定：

| 级别 | 含义 |
|------|------|
| **quick** | 定向查找 |
| **medium** | 均衡 |
| **very thorough** | 全面分析 |

> **Explore 与 Plan 启动时不加载 CLAUDE.md 与 git status 快照**，以保持调研快速廉价。

### 5.2 限制内置子代理

```json
{ "permissions": { "deny": ["Agent(Explore)", "Agent(my-custom-agent)"] } }
```

| 目的 | 做法 |
|------|------|
| 完全禁止委派 | 在 `permissions.deny` 中拒绝 `Agent` 工具本身 |
| 仅移除内置 Explore/Plan | `CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS=1` |
| 非交互/SDK 移除全部内置 | `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1` |
| CLI 单个禁用 | `claude --disallowedTools "Agent(Explore)"` |

## 六、调用方式：四级强度

| 强度 | 方式 | 语法 | 特点 |
|------|------|------|------|
| **弱** | 自动委派 | 无特殊语法 | 依据任务描述 + `description` + 当前上下文判断 |
| ↑ | 自然语言 | `Use the test-runner subagent to fix failing tests` | Claude 自行决定 |
| ↑ | **@-mention** | `@"code-reviewer (agent)" 看下认证改动` | **保证运行一次** |
| **强** | 整会话代理 | `claude --agent code-reviewer` | 主线程本身承担该子代理的工具限制与模型 |

### 6.1 `--agent` 的三个要点

1. 自定义子代理的 system prompt **完全取代**默认 Claude Code system prompt
2. 启动头显示 `@<name>` 确认生效；**恢复会话时**工具限制与模型一并恢复
3. 设为项目默认：`.claude/settings.json` 中 `{ "agent": "code-reviewer" }`

### 6.2 恢复（Resume）

子代理完成后 Claude 收到 agent ID，可用 `SendMessage` 以 ID 或 name 继续。

| 特性 | 说明 |
|------|------|
| **保留完整历史** | 含此前工具调用、结果与推理 |
| **沿用首次工具集** | 保证行为一致 |
| **可复用提示缓存** | 原运行预热过的缓存仍有效 |
| ⚠️ **Explore / Plan 无法恢复** | 它们是**一次性**的，不返回 agent ID |

## 七、工具权限

### 7.1 继承 + 两道过滤

子代理继承主对话的**内置工具 + MCP 工具**，然后被收窄：

**过滤一（无条件移除）**：
`Agent`（达嵌套上限时）、`AskUserQuestion`、`EndConversation`、`EnterPlanMode`、`ExitPlanMode`（除非 plan 模式）、`ScheduleWakeup`、`WaitForMcpServers`、`Workflow`

**过滤二（仅后台子代理）**：保留全部 MCP 工具，但内置工具仅剩
`Read`、`Grep`、`Glob`、`LSP`、`Bash`、`PowerShell`、`Edit`、`Write`、`NotebookEdit`、`WebFetch`、`WebSearch`、`TodoWrite`、`Skill`、`ToolSearch`、`EnterWorktree`、`ExitWorktree`、`Monitor`、`TaskStop`、`SendMessage`、`Artifact`、`SubagentHandback`

> **推论（重要）**：**同一定义在前台与后台可能解析出不同工具集。** 调试"工具有没有生效"时必须区分这两种运行形态。

### 7.2 白名单 / 黑名单

```yaml
# 白名单：只允许只读研究
tools: Read, Grep, Glob, Bash
```
```yaml
# 黑名单：继承除写文件外的工具
disallowedTools: Write, Edit
```

| 规则 | 说明 |
|------|------|
| 两者同设 | **先应用 `disallowedTools`，再在剩余池中解析 `tools`** |
| 同时出现在两处 | 该工具被移除 |
| `tools` 全部无法解析 | 通常**拒绝启动**并报错点名 |
| MCP 服务器级 | `mcp__github__*`（全给）、`mcp__*`（扣掉所有 MCP） |
| ⚠️ 服务器名含双下划线 | `reports__v2` 在 `tools` 中须写 `mcp__reports__v2__*`；但 `disallowedTools` 中 `mcp__reports` 会**连带扣掉 `reports__v2`** |

### 7.3 permissionMode 与主对话的交互（最反直觉的一张表）

| 主对话模式 | 子代理实际行为 |
|------------|----------------|
| `bypassPermissions` / `acceptEdits` / `auto` | 子代理**沿用相同模式**，**忽略你设置的 `permissionMode`** |
| `plan` | 子代理**保持 plan 模式**，无论你设什么 |
| `default` / `dontAsk` | 按你的设置运行（有例外） |

> **含义**：**子代理不可能比主对话更宽松。** 安全下限由主对话决定。

### 7.4 `mcpServers` 作用域化（省主上下文的关键技巧）

> **内联定义**的服务器随子代理启动连接、结束断开，**主对话看不到其工具描述**。

这解决了一个具体问题：**接了很多 MCP Server 后主对话里全是工具定义**。把工具收进子代理，主对话就干净了。

## 八、完整示例

### 8.1 目录结构

```
.claude/
└── agents/
    ├── code-reviewer.md
    ├── test-runner.md
    └── review/
        └── security.md
```

### 8.2 一个可直接用的代码评审子代理

```markdown
---
name: code-reviewer
description: Reviews code changes for quality, security, and best practices. Use proactively after any implementation change.
tools: Read, Glob, Grep, Bash
model: sonnet
maxTurns: 15
memory: project
effort: high
---
You are a senior code reviewer. You review diffs, not whole files,
unless a diff is ambiguous.

## Process
1. Run `git diff` to see what changed.
2. For each changed function, check:
   - Error handling: are failures swallowed?
   - Input validation: is untrusted input parsed at the boundary?
   - Naming: does the name say what it does?
   - Test coverage: is there a test that would fail if this broke?
3. Report findings as a list, most severe first.

## Rules
- Do NOT modify code. You are read-only by design.
- Do NOT report style nits that a formatter would catch.
- If you find nothing wrong, say "No blocking issues found" and stop.

## Memory
Before starting, check your memory for patterns you've flagged
in this repo before. After finishing, save any new recurring
pattern you noticed.
```

**这份定义用到了 8 个字段**，每一处都有明确目的：

| 字段 | 目的 |
|------|------|
| `tools` | 只读 + Bash（为了跑 git diff），**不给 Write/Edit** |
| `model: sonnet` | 评审需要较强推理 |
| `maxTurns: 15` | 防跑飞 |
| `memory: project` | 项目级记忆，可版本控制共享 |
| `effort: high` | 提高推理强度 |
| `description` 含 "Use proactively" | **提高被自动委派的概率** |
| 正文的 `## Rules` | 用 prompt 明确禁止造子代理、禁止改代码 |
| 正文的 `## Memory` | 让子代理**主动维护**自己的知识库 |

## 九、四种架构模式

### 9.1 隔离高产出操作

```
Use a subagent to run the test suite and report only
the failing tests with their error messages
```

**适用**：输出量大、主对话**之后不再引用**的内容。

### 9.2 并行调研

```
Research the authentication, database, and API modules
in parallel using separate subagents
```

**前提**：**各调研路径互不依赖**时才有效。

### 9.3 链式子代理

```
Use the code-reviewer subagent to find performance issues,
then use the optimizer subagent to fix them
```

### 9.4 maker / checker 分离（最有价值的一种）

> **写代码的模型给自己打分太宽容。**
> 第二个子代理（不同指令、有时不同模型）能抓出第一个**自我说服**的部分。

| 角色 | 配置 |
|------|------|
| **Maker** | 全工具、高推理 |
| **Checker** | 只读、独立 prompt、**不给 `Agent` 工具**（防止它再造代理） |

> 这是 Anthropic 与 Addy Osmani 共同强调的设计：**成本最低、收益最高的多 Agent 形态**。

## 十、何时用主对话 vs 子代理

| 用**主对话** | 用**子代理** |
|---|---|
| 需要频繁来回、迭代打磨 | 产生**大量不需要留在主上下文**的输出 |
| 多阶段**共享大量上下文**（规划→实现→测试） | 需要**强制特定工具限制或权限** |
| 快速、定向的小改动 | 工作**自包含**、可返回摘要 |
| **延迟敏感**（子代理需重新收集上下文） | — |

### 10.1 三个容易选错的替代方案

| 需求 | 该用什么 |
|------|----------|
| 可复用的 prompt/工作流，且要**运行在主上下文** | **Skill**，不是子代理 |
| 询问**已在对话中**的内容 | `/btw`（无工具访问，答案不进历史） |
| 需要**跨会话并行** | background agents，不是子代理 |

## 十一、限制与坑

### 11.1 规模限制

| 限制 | 默认值 | 可调 |
|------|--------|------|
| **并发子代理** | **20** 个同时 | `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` |
| **嵌套深度** | 主对话下 **3** 层 | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`（设 `1` 关闭嵌套） |
| **描述 token 上限** | **15,000**（仅警告，仍全部加载） | — |
| **预加载技能数** | 前 32 个 | — |

**几个反直觉的细节**：

- 并发上限**只拦截** Claude 通过 Agent 工具派生的子代理
- `/subtask` 的 fork **占槽但从不被拦**
- **恢复已完成的子代理会占新槽且不检查上限**，可能把运行数推过上限

### 11.2 功能与数据限制

| 限制 | 说明 |
|------|------|
| **Explore / Plan 一次性** | 无 agent ID，**无法恢复** |
| **无独立 extended thinking 设置** | 继承主对话设置 |
| **上下文窗口跟随自身模型** | 配小模型就得小窗口 |
| **名字跨重启的脆弱性** | 自上次压缩以来的名字能跨重启存活，压缩前的不能 |
| **transcript 自动清理** | 默认 30 天（`cleanupPeriodDays`） |
| **手动停掉的子代理不会自动恢复** | Claude 发消息会被拒绝 |

### 11.3 五个高频故障

| 症状 | 原因与解法 |
|------|-----------|
| 自定义子代理**永远不被调用** | `description` 写太模糊；加 "use proactively" |
| 字段写了但**不生效** | 拼写错（camelCase）或被静默忽略；用 `claude --debug` 搜 `does not recognize or apply` |
| `subagent_type is required` | `Agent` 调用省略了 `subagent_type` 且无 `general-purpose` 兜底 |
| 前台子代理报 `terminated early due to an API error` | 未产生输出或仅有工具调用；**若已有文本输出则会返回部分结果** |
| 报告开头出现 `⚠ This agent switched to <model>...` | 模型不可用，切到了 fallback |

## 十二、与相邻概念的关系

```
Skill           → 方法层：怎么做（可主上下文运行，可复用）
Sub Agent       → 隔离层：谁来做（独立上下文 + 受限工具）
MCP             → 能力层：能做什么（外部工具与数据）
Loop Engineering→ 时间层：何时反复做（调度 + 终止）
```

| 想解决 | 用什么 |
|--------|--------|
| 项目知识/流程写下来复用 | **Skill** |
| 高产出操作不污染主上下文 | **Sub Agent** |
| 接入外部系统 | **MCP** |
| 让整套东西自己反复跑 | **Loop Engineering** |
| 结果需要独立验证 | **Sub Agent（checker 角色）** |

## 十三、Checklist

**定义前**
- [ ] 这个任务真的**产出量大**且我**之后不会再引用**吗？
- [ ] 它**自包含**、能返回摘要吗？
- [ ] 用 Skill 是不是更合适？（需要主上下文时）

**定义时**
- [ ] `name` 唯一，无 `:`、不以 `-` 开头
- [ ] `description` 写清"何时委派"，必要时加 "use proactively"
- [ ] `tools` 用**最小集**（只读任务别给 Write/Edit）
- [ ] 只读 reviewer **不给 `Agent` 工具**（防它再生代理）
- [ ] `model` 与任务难度匹配（别用 haiku 干重活）
- [ ] 设 `maxTurns` 兜底
- [ ] 需要跨会话积累知识时配 `memory: project`

**运维**
- [ ] 项目级放 `.claude/agents/` 并**纳入版本控制**
- [ ] 用 `/doctor` 检查重名
- [ ] 定期 `claude --debug` 检查字段是否被静默忽略
- [ ] 关注并发（20）与嵌套（3）上限
- [ ] 需要隔离文件改动时用 `isolation: worktree`

**安全**
- [ ] 明白**输出扫描不判断恶意**，不能替代范围限制
- [ ] 主对话权限模式决定了子代理的**安全下限**
- [ ] 插件子代理**不支持** `hooks` / `mcpServers` / `permissionMode`
- [ ] 内联 MCP 服务器需先信任所在文件夹

## 十四、总结

**子代理的四条本质：**

| 本质 | 含义 |
|------|------|
| **不是"多一个 AI"，是"多一个上下文垃圾桶"** | 核心价值在**隔离**，不在并行 |
| **不是副本，是白纸** | 只拿到 system prompt + 任务摘要 + CLAUDE.md + git status |
| **不能比主对话更宽松** | 权限只会被收窄，不会放宽 |
| **一次性 vs 可恢复要分清** | Explore/Plan 用完即弃 |

**四条最值得记住的原则**：

1. **用它的理由必须是"隔离"，不是"更强"** —— 需要共享上下文时，子代理是错的
2. **`description` 是唯一的触发开关** —— 写模糊就等于不存在
3. **只读的检查者不要给 `Agent` 工具** —— 否则它会自己造一窝子代理
4. **maker / checker 分离是性价比最高的用法** —— 一个节点换来独立验证

> **最后一句话**：
> **子代理不是"更聪明的助手"，而是"更窄的上下文"。**
> 它的收益来自**你不再看到的东西**，而不是它做得比你好。

---

> **资料说明**
> 本文官方定义、19 个 frontmatter 字段、优先级、内置子代理、四级调用、两道工具过滤、permissionMode 交互表、并发/嵌套限制、故障排查等，**全部依据 Claude Code 官方文档《Create custom subagents》** 整理。
> maker/checker 分离与"写代码的模型给自己打分太宽容"，依据 **Anthropic 多 Agent 研究系统**与 **Addy Osmani《Loop Engineering》**。
> "上下文切碎的代价"这一约束，依据 **Cognition《Don't Build Multi-Agents》**。
>
> **重要限制**：
> - 官方文档页面**在"Set the auto-compact window for one subagent"章节处被截断**，该章节后续内容未获取。
> - 文档中出现的**版本号**（v2.1.281+、v2.1.267+、v2.1.257+、v2.1.198+、v2.1.299 等）表明内容较新，但**字段与默认值随版本变化**，接入前请核对当前文档。
> - 文中所有**字段名与默认值（20 并发 / 3 层嵌套 / 15,000 token）为抓取时状态**，可能已调整。
> - 所有引文为**中文意译**，非逐字直译。
