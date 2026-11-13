<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'

import {
  chatStream,
  type ChatMessage,
  type ChatUsage,
  type ContextUsage,
  type ToolEvent,
  type TracePayload,
  type TraceStep,
} from '../api/chat'
import { ApiError } from '../api/http'

/**
 * 一次最多带多少条历史。
 *
 * 不裁剪的话，聊到第 30 轮就会超过后端的 50 条上限，直接 422 ——
 * 用户看到的是"聊着聊着突然发不出去了"。
 * 这个值和后端 ChatRequest 的 max_length 是配套的。
 */
const MAX_HISTORY = 20

/**
 * 界面上的一个气泡。
 *
 * 比后端的 ChatMessage 多一个 reasoning：
 *   - content   最终答案，也是唯一要回传给模型的历史
 *   - reasoning 推理模型的思考过程，只用于展示，**绝不能再喂回去** ——
 *               把模型自己的草稿当历史发回去既浪费 token，又可能干扰后续推理
 */
interface Bubble {
  role: 'user' | 'assistant'
  content: string
  reasoning: string
  /** 思考区是否展开。生成过程中强制展开，结束后自动收起 */
  reasoningOpen: boolean
  /**
   * 这一轮里模型调用过的工具，按到达顺序排列。
   * 同一个 id 会收到两帧（running → done/error），所以是"就地更新"而不是追加。
   * 仅在生成过程中使用 —— 结束后由 trace 接管展示。
   */
  tools: ToolEvent[]
  /** 结束后由后端下发的完整 trace，用来渲染步骤时间线 */
  trace: TracePayload | null
  /** 本次对话的 token / 成本统计 */
  usage: ChatUsage | null
  /** S4：上下文预算 */
  contextUsage: ContextUsage | null
  /** 哪几步是展开的。默认全折叠：过程要看得见，但不该盖过答案 */
  openSteps: number[]
}

const messages = ref<Bubble[]>([])
const draft = ref('')
const running = ref(false)
const error = ref('')
const listEl = ref<HTMLElement | null>(null)

let controller: AbortController | null = null

const canSend = computed(() => !running.value && draft.value.trim().length > 0)

/** 虚拟渲染上限：超过后只渲染最近 N 条，DOM 节点数不会无限增长 */
const MESSAGE_MAX = 200
const displayMessages = computed(() => {
  if (messages.value.length <= MESSAGE_MAX) return messages.value
  return messages.value.slice(messages.value.length - MESSAGE_MAX)
})

/** v-memo 缓存键：只在这几项变了才重渲染。颜色和折叠状态由 CSS 处理。 */
function messageMemo(m: Bubble): [number, number, boolean, boolean] {
  return [m.content.length, m.tools.length, !!m.trace, !!m.usage]
}

// ---- S3：文档上传 ----
const fileEl = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadMsg = ref('')

async function handleUpload(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true; uploadMsg.value = ''
  try {
    const form = new FormData(); form.append('file', file)
    const resp = await fetch('/api/v1/rag/upload', { method: 'POST', body: form })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error((err as { message?: string; detail?: string }).message
        || (err as { message?: string; detail?: string }).detail
        || `HTTP ${resp.status}`)
    }
    const data = await resp.json() as { title?: string; chunks?: number }
    uploadMsg.value = `已索引《${data.title ?? file.name}》，${data.chunks ?? 0} 个片段`
  } catch (e) {
    uploadMsg.value = '上传失败：' + (e instanceof Error ? e.message : '未知错误')
  } finally { uploading.value = false; input.value = '' }
}

// ---- S3：引用提取 ----

interface RAGRef { heading: string; snippet: string }

function ragRefs(m: Bubble): RAGRef[] {
  if (!m.trace) return []
  const out: RAGRef[] = []
  for (const step of m.trace.steps) {
    for (const tc of step.tool_calls) {
      if (tc.name !== 'search_docs') continue
      const result = tc.result as { chunks?: { heading?: string; content?: string }[] } | null
      if (!result?.chunks) continue
      for (const c of result.chunks) {
        out.push({ heading: c.heading || '', snippet: (c.content || '').slice(0, 200) })
      }
    }
  }
  return out
}

function ragMs(m: Bubble): number {
  return Math.round(m.trace?.duration_ms || 0)
}

// ---- S4：上下文预算 ----
function budgetClass(ratio: number): string {
  if (ratio > 0.9) return 'budget--danger'
  if (ratio > 0.8) return 'budget--warn'
  return ''
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === 'AbortError'
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const el = listEl.value
  if (el) el.scrollTop = el.scrollHeight
}

/** 气泡里有没有任何值得保留的东西。工具调用记录也算 —— 模型动过手就是有效信息。 */
function isEmpty(bubble: Bubble): boolean {
  return !bubble.content && !bubble.reasoning && bubble.tools.length === 0
}

function toolIcon(status: ToolEvent['status']): string {
  if (status === 'running') return '◌'
  if (status === 'error') return '✕'
  return '✓'
}

/** 把 {title: "明天交周报"} 渲染成 title="明天交周报" */
function formatArgs(args: unknown): string {
  if (!args || typeof args !== 'object') return ''
  const entries = Object.entries(args as Record<string, unknown>)
  if (!entries.length) return ''
  return entries.map(([key, value]) => `${key}=${JSON.stringify(value)}`).join(' ')
}

/** 一行结果摘要。数字和 id 比一整段 JSON 好读得多。 */
function summarize(tool: { status: string; result?: unknown }): string {
  if (tool.status === 'running') return '执行中…'

  const obj =
    typeof tool.result === 'object' && tool.result !== null
      ? (tool.result as Record<string, unknown>)
      : null

  if (tool.status === 'error') {
    const msg = obj?.error
    return typeof msg === 'string' ? msg : '失败'
  }

  if (obj) {
    if (typeof obj.count === 'number') return `${obj.count} 条`
    const todo = obj.todo
    if (todo && typeof todo === 'object') {
      const id = (todo as Record<string, unknown>).id
      if (typeof id === 'number') return `#${id}`
    }
    if (typeof obj.deleted_id === 'number') return `已删除 #${obj.deleted_id}`
  }
  return '完成'
}

/** 展开 / 收起某一步 */
function toggleStep(bubble: Bubble, step: number): void {
  const index = bubble.openSteps.indexOf(step)
  if (index >= 0) bubble.openSteps.splice(index, 1)
  else bubble.openSteps.push(step)
}

/** 步骤标题：没调工具就是"直接回答"，调了就把工具名列出来 */
function stepLabel(step: TraceStep): string {
  if (!step.tool_calls.length) return '直接回答'
  return step.tool_calls.map((t) => t.name).join(' + ')
}

/** 非正常结束的原因，给用户看的一句人话 */
function stopText(reason: string): string {
  if (reason === 'max_steps') return '已达步数上限，被迫收尾'
  if (reason === 'cost_limit') return '已达成本上限，已停止'
  if (reason === 'disconnected') return '已中断'
  return ''
}

async function send(): Promise<void> {
  if (!canSend.value) return

  const text = draft.value.trim()
  draft.value = ''
  error.value = ''

  messages.value.push({
    role: 'user',
    content: text,
    reasoning: '',
    reasoningOpen: false,
    tools: [],
    trace: null,
    usage: null,
    contextUsage: null,
    openSteps: [],
  })

  // 先放一个空的 assistant 气泡，后面每来一个 delta 就往里追加。
  // 这样用户看到的是"文字一个个冒出来"，而不是等全部结束才突然出现一大段。
  messages.value.push({
    role: 'assistant',
    content: '',
    reasoning: '',
    reasoningOpen: true,
    tools: [],
    trace: null,
    usage: null,
    contextUsage: null,
    openSteps: [],
  })

  // 必须从数组里取回代理对象。
  // 直接持有 push 进去的那个字面量的话，改它的 .content 不会触发视图更新 ——
  // Vue 拦截的是「通过代理的读写」，原始对象被修改时它毫不知情。
  const reply = messages.value[messages.value.length - 1]!

  // 去掉刚加进来的空气泡，只把之前的历史送上去。
  // 只映射 role + content：reasoning 是模型的内部草稿，不回传。
  const history: ChatMessage[] = messages.value
    .slice(0, -1)
    .slice(-MAX_HISTORY)
    .map((m) => ({ role: m.role, content: m.content }))

  running.value = true
  controller = new AbortController()
  await scrollToBottom()

  try {
    await chatStream({
      messages: history,
      signal: controller.signal,
      onChunk: (chunk) => {
        // 思考帧先到：推理模型会连推几十帧 reasoning 才开始吐答案。
        // 不显示的话，用户在这段时间里看到的是一个空白的空气泡，会以为卡死了。
        if (chunk.reasoning) {
          reply.reasoning += chunk.reasoning
          void scrollToBottom()
        }
        // 工具帧：同一个 id 会来两次（开始 / 结束），就地覆盖。
        // 如果无脑 push，用户会看到"正在调用 list_todos"和"已完成 list_todos"
        // 两条并列的尴尬记录。
        if (chunk.tool) {
          const incoming = chunk.tool
          const existing = reply.tools.find((t) => t.id === incoming.id)
          if (existing) Object.assign(existing, incoming)
          else reply.tools.push({ ...incoming })
          void scrollToBottom()
        }
        if (chunk.delta) {
          reply.content += chunk.delta
          void scrollToBottom()
        }

        // done 帧带回来的统计与完整 trace：
        // 有 trace 之后，界面从"实时工具胶囊"切换成"步骤时间线"
        if (chunk.usage) reply.usage = chunk.usage
        if (chunk.context_usage) reply.contextUsage = chunk.context_usage
        if (chunk.trace) reply.trace = chunk.trace
      },
    })
  } catch (e) {
    if (isAbort(e)) {
      // 用户主动停止：已经收到的内容保留，那本身就是有价值的部分
      if (isEmpty(reply)) messages.value.pop()
    } else {
      error.value = e instanceof ApiError ? e.message : '对话失败'
      // 什么都没有就删掉空气泡，否则会留下一个空白框
      if (isEmpty(reply)) messages.value.pop()
    }
  } finally {
    // 生成结束：把思考区收起来，让答案成为视觉重点。
    // 但如果一个字答案都没有，就别收 —— 否则气泡会变成一片空白，
    // 用户会以为请求失败了（实际上模型只是把额度全用在思考上了）。
    reply.reasoningOpen = !reply.content

    running.value = false
    controller = null

    // 折叠会改变高度，重新贴到底部，否则用户会看到内容"跳一下"
    if (reply.reasoning) void scrollToBottom()
  }
}

function stop(): void {
  // 传 reason，Chrome 的日志就变成「AbortError: 用户主动停止」而不是 without reason
  controller?.abort(new DOMException('用户主动停止', 'AbortError'))
}

function clear(): void {
  if (running.value) return
  messages.value = []
  error.value = ''
}

// 组件卸载时一定要中断，否则离开页面后上游还在生成（按 token 计费）
onBeforeUnmount(() => stop())
</script>

<template>
  <section class="panel">
    <div class="panel__head">
      <h2>
        对话
        <span class="panel__badge">LLM</span>
      </h2>
      <button
        v-if="messages.length"
        class="btn btn--ghost"
        type="button"
        :disabled="running"
        @click="clear"
      >
        清空
      </button>
    </div>

    <div ref="listEl" class="chat">
      <p v-if="!messages.length" class="state">输入一个问题，回复会逐字出现。</p>

      <!-- 消息超过上限时，上方提示裁剪 -->
      <p v-if="messages.length > MESSAGE_MAX" class="chat__trimmed">
        ↑ 仅显示最近 {{ MESSAGE_MAX }} 条（共 {{ messages.length }} 条，更早的消息未渲染）
      </p>

      <div
        v-for="(m, i) in displayMessages"
        :key="i"
        v-memo="messageMemo(m)"
        class="chat__row"
        :class="`chat__row--${m.role}`"
      >
        <div class="chat__bubble">
          <!--
            思考区：生成中显示「正在思考…」并实时滚字，结束后自动折叠成
            「已思考 N 字 ▾」，点一下可以重新展开。
            折叠的意义在于——思考内容常常比答案长十倍，一直摊开会把答案挤到看不见。
          -->
          <div v-if="m.reasoning" class="chat__reasoning">
            <div v-if="running && i === displayMessages.length - 1" class="chat__reasoning-head chat__reasoning-head--live">
              正在思考…（{{ m.reasoning.length }} 字）
            </div>
            <button
              v-else
              class="chat__reasoning-head"
              type="button"
              @click="m.reasoningOpen = !m.reasoningOpen"
            >
              已思考 {{ m.reasoning.length }} 字
              <span class="chat__reasoning-chev">{{ m.reasoningOpen ? '▴' : '▾' }}</span>
            </button>

            <div v-if="m.reasoningOpen" class="chat__reasoning-body">{{ m.reasoning }}</div>
          </div>

          <!--
            步骤时间线：这是 S2 与"只会调 API 的人"的分水岭。
            默认折叠 —— 扫一眼是"第 1 步 list_todos · 917ms · 777tk"，
            想深究再点开看模型当时说了什么、工具返回了什么。
          -->
          <div v-if="m.trace && m.trace.steps.length" class="timeline">
            <div v-for="s in m.trace.steps" :key="s.step" class="timeline__step">
              <button class="timeline__head" type="button" @click="toggleStep(m, s.step)">
                <span class="timeline__no">第 {{ s.step + 1 }} 步</span>
                <span class="timeline__label">{{ stepLabel(s) }}</span>
                <span class="timeline__meta">
                  {{ Math.round(s.duration_ms) }}ms · {{ s.prompt_tokens + s.completion_tokens }} tk
                </span>
                <span class="timeline__chev">{{ m.openSteps.includes(s.step) ? '▴' : '▾' }}</span>
              </button>

              <div v-if="m.openSteps.includes(s.step)" class="timeline__body">
                <p v-if="s.reasoning" class="timeline__thought">{{ s.reasoning }}</p>
                <p v-if="s.model_output" class="timeline__say">{{ s.model_output }}</p>
                <div
                  v-for="(t, ti) in s.tool_calls"
                  :key="ti"
                  class="timeline__tool"
                  :class="{ 'timeline__tool--error': t.status === 'error' }"
                >
                  <span class="timeline__branch">└</span>
                  <span class="timeline__tool-name">{{ t.name }}</span>
                  <span class="timeline__tool-args">({{ formatArgs(t.arguments) }})</span>
                  <span class="timeline__tool-arrow">→</span>
                  <span class="timeline__tool-result">{{ summarize(t) }}</span>
                  <span class="timeline__tool-ms">{{ Math.round(t.duration_ms) }}ms</span>
                </div>
              </div>
            </div>
          </div>

          <!--
            生成过程中还没有 trace：先用实时胶囊顶着，
            让用户立刻看到"正在查什么"，而不是盯着空气泡。
          -->
          <div v-else-if="m.tools.length" class="chat__tools">
            <div
              v-for="t in m.tools"
              :key="t.id"
              class="tool-call"
              :class="`tool-call--${t.status}`"
            >
              <span class="tool-call__icon">{{ toolIcon(t.status) }}</span>
              <span class="tool-call__name">{{ t.name }}</span>
              <span class="tool-call__args">{{ formatArgs(t.arguments) }}</span>
              <span class="tool-call__result">{{ summarize(t) }}</span>
            </div>
          </div>

          <div v-if="m.content" class="chat__content">{{ m.content }}</div>

          <!-- 用量与成本：一次对话花了几厘钱，摊开给用户看，不用猜 -->
          <div v-if="m.usage" class="chat__stats">
            <span>{{ m.usage.total_tokens }} tokens</span>
            <span>¥{{ m.usage.cost_cny.toFixed(6) }}</span>
            <span v-if="m.trace">{{ (m.trace.duration_ms / 1000).toFixed(2) }}s</span>
            <span v-if="m.usage.tool_calls">{{ m.usage.tool_calls }} 次工具</span>
            <span v-if="stopText(m.usage.stopped_reason)" class="chat__stats-warn">
              {{ stopText(m.usage.stopped_reason) }}
            </span>
          </div>

          <!-- S4：上下文预算进度条 -->
          <div v-if="m.contextUsage" class="budget">
            <div class="budget__head">
              上下文预算：{{ m.contextUsage.used_tokens }} / {{ m.contextUsage.budget_tokens }} token
              <span :class="budgetClass(m.contextUsage.ratio)">{{ (m.contextUsage.ratio * 100).toFixed(0) }}%</span>
            </div>
            <div class="budget__bar">
              <div
                class="budget__fill"
                :class="budgetClass(m.contextUsage.ratio)"
                :style="{ width: Math.min(m.contextUsage.ratio * 100, 100) + '%' }"
              />
            </div>
          </div>

          <!-- 引用来源：从 search_docs 工具调用结果中提取 -->
          <div v-if="ragRefs(m).length" class="refs">
            <div class="refs__head">
              检索到 {{ ragRefs(m).length }} 个引用，用时 {{ ragMs(m) }}ms
            </div>
            <div v-for="(ref, ri) in ragRefs(m)" :key="ri" class="refs__item">
              <span class="refs__idx">[{{ ri + 1 }}]</span>
              <span class="refs__heading">{{ ref.heading }}</span>
              <div class="refs__snippet">{{ ref.snippet }}</div>
            </div>
          </div>

          <span v-if="running && i === displayMessages.length - 1" class="caret" />
        </div>
      </div>
    </div>

    <p v-if="error" class="alert">{{ error }}</p>

    <!-- S3：文档上传。拖拽区和文件选择，上传后自动索引用。 -->
    <div class="upload">
      <input type="file" ref="fileEl" class="upload__input" accept=".md,.txt,.pdf" @change="handleUpload" />
      <button type="button" class="upload__btn" @click="fileEl?.click()" :disabled="running || uploading">
        {{ uploading ? '解析中…' : '📁 上传文档' }}
      </button>
      <span class="upload__hint">支持 md / txt / pdf，问知识库里的内容</span>
      <span v-if="uploadMsg" class="upload__msg">{{ uploadMsg }}</span>
    </div>

    <form class="row" @submit.prevent="send">
      <input
        v-model="draft"
        class="input"
        type="text"
        placeholder="问点什么…"
        maxlength="2000"
        :disabled="running"
      />
      <button v-if="!running" class="btn btn--primary" type="submit" :disabled="!canSend">
        发送
      </button>
      <button v-else class="btn btn--danger" type="button" @click="stop()">停止</button>
    </form>
  </section>
</template>
