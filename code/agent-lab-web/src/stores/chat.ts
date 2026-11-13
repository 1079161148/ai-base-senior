import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ToolEvent, ChatUsage, ContextUsage, TracePayload } from '../api/chat'
import { chatStreamV2 } from '../api/chat'
import { ApiError } from '../api/http'
import { useSessionStore } from './session'

export interface Message {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  /** 思考过程（推理模型） */
  reasoning: string
  reasoningOpen: boolean
  /** 本轮的实时工具调用状态 */
  tools: ToolEvent[]
  trace: TracePayload | null
  usage: ChatUsage | null
  contextUsage: ContextUsage | null
}

export const useChatStore = defineStore('chat', () => {
  // ---- State ----
  const messages = ref<Message[]>([])
  const running = ref(false)
  const error = ref('')
  let _nextId = 1
  let _controller: AbortController | null = null

  // ---- Computed ----
  const lastMessage = computed(() => messages.value[messages.value.length - 1] ?? null)

  // ---- Actions ----
  function pushUser(content: string) {
    messages.value.push({
      id: _nextId++, role: 'user', content,
      reasoning: '', reasoningOpen: false,
      tools: [], trace: null, usage: null, contextUsage: null,
    })
  }

  function pushAssistant(): Message {
    messages.value.push({
      id: _nextId++, role: 'assistant', content: '',
      reasoning: '', reasoningOpen: false,
      tools: [], trace: null, usage: null, contextUsage: null,
    })
    // 必须从数组里取回**代理对象**再返回。
    // 直接返回上面那个原始对象的话，后续 reply.content += delta 改的是裸对象，
    // 绕过了 reactive 的 set 拦截，不会触发重渲染 ——
    // 表现就是「整段回答在流结束的瞬间一次性蹦出来」，没有打字机效果。
    return messages.value[messages.value.length - 1]!
  }

  async function send(content: string) {
    if (running.value) return
    error.value = ''

    const sessionStore = useSessionStore()

    pushUser(content)
    const reply = pushAssistant()

    _controller = new AbortController()
    running.value = true

    try {
      // 走 /chat/stream-v2：只发 session_id + 当前问题。
      // 历史、记忆、预算都由服务端负责，前端不再把整段 history 塞回去。
      // session_id 为 null 时后端会自动建会话，并在 done 帧里回传 id。
      await chatStreamV2({
        sessionId: sessionStore.currentId,
        content,
        signal: _controller.signal,
        onChunk(chunk) {
          if (chunk.reasoning) {
            reply.reasoning += chunk.reasoning
            reply.reasoningOpen = true
          }
          if (chunk.delta) {
            reply.content += chunk.delta
          }
          if (chunk.tool) {
            const existing = reply.tools.find(t => t.id === chunk.tool!.id)
            if (existing) Object.assign(existing, chunk.tool)
            else reply.tools.push(chunk.tool)
          }
          if (chunk.done) {
            reply.reasoningOpen = false
            if (chunk.usage) reply.usage = chunk.usage
            if (chunk.trace) reply.trace = chunk.trace
            if (chunk.context_usage) reply.contextUsage = chunk.context_usage
            // 第一轮对话：把后端新分配的会话 id 记下来
            if (chunk.session_id) sessionStore.setCurrent(chunk.session_id)
          }
        },
      })
    } catch (e) {
      const aborted = e instanceof DOMException && e.name === 'AbortError'
      if (!aborted) {
        error.value = e instanceof ApiError ? e.message : '发送失败，请重试'
      }

      // 一个字都没吐出来就失败了（比如 400 / 503）时，把占位气泡删掉。
      // 否则界面会留一个空白框，用户不知道那是空的还是还没开始。
      if (!reply.content && !reply.reasoning) {
        const idx = messages.value.indexOf(reply)
        if (idx !== -1) messages.value.splice(idx, 1)
      }

      if (aborted) return
    } finally {
      running.value = false
      _controller = null
      // 标题和消息数都变了，刷新一次列表，让「会话」页立刻能看到
      if (sessionStore.currentId) await sessionStore.fetchAll()
    }
  }

  /** 从服务端拉某个会话的完整消息，用于「会话」页点进去继续聊 */
  async function loadSession(id: string) {
    const res = await fetch(`/api/v1/sessions/${id}`)
    if (!res.ok) throw new Error(`加载会话失败（${res.status}）`)

    const data = (await res.json()) as {
      messages: Array<{ role: string; content: string | null }>
    }

    // tool 消息不进气泡：它已经在 trace 里体现过了
    messages.value = data.messages
      .filter(m => (m.role === 'user' || m.role === 'assistant') && (m.content ?? '').trim().length > 0)
      .map(m => ({
        id: _nextId++,
        role: m.role as 'user' | 'assistant',
        content: m.content ?? '',
        reasoning: '',
        reasoningOpen: false,
        tools: [],
        trace: null,
        usage: null,
        contextUsage: null,
      }))
    error.value = ''
  }

  function stop() {
    _controller?.abort()
    running.value = false
  }

  /**
   * 重新生成某条回答：丢弃这条回答和它前面那条提问，用同样的内容重发一次。
   *
   * 只允许对**最后一条** assistant 使用。原因在服务端：
   * 没有"删除历史消息"的接口，重新生成等于在会话里**再问一次**，
   * 历史会追加一组问答。对中间某条回答重新生成的话，
   * 界面上看着替换了，刷新后旧问答又冒出来，用户会以为数据错乱。
   *
   * 返回 false 表示这次操作被拒绝（正在生成、或不是最后一条）。
   */
  async function regenerate(assistantId: number): Promise<boolean> {
    if (running.value) return false

    const last = messages.value[messages.value.length - 1]
    if (!last || last.id !== assistantId) return false

    const pos = messages.value.findIndex(m => m.id === assistantId)
    if (pos <= 0) return false

    // 往前找最近的 user —— 界面上永远是 user → assistant 成对出现
    const user = messages.value[pos - 1]
    if (!user || user.role !== 'user') return false

    const text = user.content
    // 截到这条提问之前：send() 会重新 push 一对 user / assistant
    messages.value = messages.value.slice(0, pos - 1)
    await send(text)
    return true
  }

  function clear() {
    messages.value = []
    error.value = ''
  }

  return {
    messages,
    running,
    error,
    lastMessage,
    send,
    stop,
    regenerate,
    clear,
    loadSession,
  }
})