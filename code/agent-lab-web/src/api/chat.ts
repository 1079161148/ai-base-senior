/**
 * 对话接口（S1）。
 *
 * 和 `stream.ts` 的区别只有一个：请求是 POST 且带 JSON body，
 * 流的解析完全复用 `readSSE`。
 */

import { ApiError } from './http'
import { readSSE } from './stream'

export type ChatRole = 'system' | 'user' | 'assistant'

export interface ChatMessage {
  role: ChatRole
  content: string
}

/** 一次工具调用的状态。同一个 id 会来两帧：先 running，后 done / error */
export interface ToolEvent {
  id: string
  name: string
  /** 已经过 JSON.parse 的参数对象，直接展示用 */
  arguments?: unknown
  status: 'running' | 'done' | 'error'
  /** 工具返回结果，running 阶段没有 */
  result?: unknown
}

/** 一次工具调用的可回放记录（来自 trace） */
export interface TraceTool {
  name: string
  arguments: unknown
  result: unknown
  status: string
  duration_ms: number
}

/** Agent 的一步：模型这一轮说了什么、调了什么 */
export interface TraceStep {
  step: number
  model_output: string
  reasoning: string
  tool_calls: TraceTool[]
  prompt_tokens: number
  completion_tokens: number
  duration_ms: number
}

/** 后端落盘的完整 trace，随 done 帧一起下发 */
export interface TracePayload {
  trace_id: string
  started_at: string
  model: string
  question: string
  duration_ms: number
  steps: TraceStep[]
  usage: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
    cost_cny?: number
    tool_calls?: number
  }
  stopped_reason: string
}

/** 结束帧的统计 */
export interface ChatUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  /** 人民币，6 位小数 */
  cost_cny: number
  chars: number
  reasoning_chars: number
  tool_calls: number
  stopped_reason: string
}

/** S4：上下文预算使用情况 */
export interface ContextUsage {
  used_tokens: number
  budget_tokens: number
  ratio: number
  breakdown: Record<string, number>
}

/** 与后端 chat.py 的帧结构对应 */
export interface ChatChunk {
  /** 答案正文的增量 */
  delta?: string
  /** 推理模型的思考增量（普通模型不会出现），与 delta 分开两路 */
  reasoning?: string
  /** 工具调用状态帧 */
  tool?: ToolEvent
  done?: boolean
  usage?: ChatUsage
  /** 本次对话的 trace id，可用于事后查 /api/v1/traces/{id} */
  trace_id?: string
  /** 完整 trace，前端直接拿来渲染时间线 */
  trace?: TracePayload
  /** S4：上下文预算 */
  context_usage?: ContextUsage
  /** S4：会话 ID */
  session_id?: string
  error?: { code: string; message: string }
}

export interface ChatStreamOptions {
  messages: ChatMessage[]
  signal?: AbortSignal
  onChunk: (chunk: ChatChunk) => void
}

/** S4：按会话发消息。历史由服务端维护，前端只发当前问题。 */
export interface ChatStreamV2Options {
  /** 为 null 时后端自动建会话，并在 done 帧里回传 session_id */
  sessionId: string | null
  content: string
  signal?: AbortSignal
  onChunk: (chunk: ChatChunk) => void
}

/** 后端错误响应体（与 http.ts 里的形状一致） */
interface ApiErrorBody {
  code?: string
  message?: string
}

export async function chatStream({
  messages,
  signal,
  onChunk,
}: ChatStreamOptions): Promise<void> {
  const res = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ messages }),
    signal,
  })

  await assertOk(res)
  await readSSE<ChatChunk>(res, (chunk) => {
    throwIfChunkError(chunk)
    onChunk(chunk)
  })
}

/**
 * S4：按会话发消息。
 *
 * 和 `/chat/stream` 的区别只在**请求体**：那边每次把完整 history 塞过来，
 * 这边只发 session_id + 当前问题，历史由服务端的三层记忆负责拼装。
 * 响应流的结构完全一样，所以解析逻辑可以复用。
 */
export async function chatStreamV2({
  sessionId,
  content,
  signal,
  onChunk,
}: ChatStreamV2Options): Promise<void> {
  const res = await fetch('/api/v1/chat/stream-v2', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ session_id: sessionId, content }),
    signal,
  })

  await assertOk(res)
  await readSSE<ChatChunk>(res, (chunk) => {
    throwIfChunkError(chunk)
    onChunk(chunk)
  })
}

/** 流还没开始就失败（如 503 LLM_NOT_CONFIGURED）：此时是标准 JSON 错误体 */
async function assertOk(res: Response): Promise<void> {
  if (res.ok) return

  const text = await res.text()
  let code = 'CHAT_FAILED'
  let message = `对话请求失败（${res.status}）`

  try {
    const body = JSON.parse(text) as ApiErrorBody
    if (body.code) code = body.code
    if (body.message) message = body.message
  } catch {
    // 不是 JSON（比如网关返回的 HTML），保留默认文案
  }

  throw new ApiError(res.status, code, message)
}

/** 流内错误：HTTP 已经是 200，后端只能发一帧 {"error": {...}} */
function throwIfChunkError(chunk: ChatChunk): void {
  if (chunk.error) {
    throw new ApiError(502, chunk.error.code, chunk.error.message)
  }
}
