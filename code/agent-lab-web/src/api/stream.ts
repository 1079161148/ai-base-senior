/**
 * SSE 流式消费。
 *
 * **为什么不用 EventSource**（面试常问）：
 *   1. 只能发 GET —— S1 要把整段对话历史 POST 上去，它做不到
 *   2. 不能自定义请求头 —— 没法带 Authorization
 *   3. 不能传 signal —— 无法优雅中断
 *
 * 所以统一用 `fetch + ReadableStream` 手动按 SSE 规则解析。
 *
 * 本文件只保留**一份**解析实现：`readSSE` 被 demo 流和 chat 流共用。
 * 复制粘贴两份的话，改协议时必然漏掉一处。
 */

import { ApiError } from './http'

/** 与后端 demo.py 的 payload 对应 */
export interface StreamChunk {
  delta?: string
  index?: number
  done?: boolean
  usage?: { chars: number; cost_cny: number }
}

export interface StreamDemoOptions {
  text: string
  signal?: AbortSignal
  onChunk: (chunk: StreamChunk) => void
}

const EVENT_SEPARATOR = '\n\n'
const DATA_FIELD = 'data:'

function dispatch<T>(raw: string, onEvent: (payload: T) => void): void {
  for (const line of raw.split('\n')) {
    if (!line.startsWith(DATA_FIELD)) continue

    // SSE 规范里 `data:` 之后的那个空格是**可选**的：
    //   data:{"a":1}      ← 合法
    //   data: {"a":1}     ← 合法
    // 之前只认带空格的写法，遇到不带空格的实现会静默丢掉整条消息。
    let payload = line.slice(DATA_FIELD.length)
    if (payload.startsWith(' ')) {
      payload = payload.slice(1)
    }
    payload = payload.trim()
    if (!payload) continue

    // 只把「解析」包进 try。如果把 onEvent 也包进来，
    // 调用方在回调里抛的错误（比如流内 error 帧要中断）会被静默吞掉 ——
    // 表现为"后端明明报了错，前端却什么都没发生"。
    let parsed: unknown
    try {
      parsed = JSON.parse(payload)
    } catch {
      // 单条消息坏掉不该中断整个流，跳过即可
      continue
    }

    onEvent(parsed as T)
  }
}

/**
 * 把一个 text/event-stream 响应逐帧读出来。
 *
 * 调用方只需关心「收到一帧要做什么」，切包、粘包、解码残片都由这里处理。
 * 泛型 T 让 demo 和 chat 各自描述自己的帧结构，不用 `any`。
 */
export async function readSSE<T>(res: Response, onEvent: (payload: T) => void): Promise<void> {
  if (!res.body) {
    throw new ApiError(0, 'NO_BODY', '响应没有可读的数据流')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      // stream: true —— 一个中文字符可能被拆在两次 chunk 里，必须让解码器保留残片
      buffer += decoder.decode(value, { stream: true })

      // 一个事件可能跨多个 chunk，也可能一个 chunk 里有多条事件，所以要循环切分
      let sepIndex = buffer.indexOf(EVENT_SEPARATOR)
      while (sepIndex !== -1) {
        dispatch<T>(buffer.slice(0, sepIndex), onEvent)
        buffer = buffer.slice(sepIndex + EVENT_SEPARATOR.length)
        sepIndex = buffer.indexOf(EVENT_SEPARATOR)
      }
    }

    // 流结束时 buffer 里可能还留着没有结尾空行的最后一条
    if (buffer.trim()) {
      dispatch<T>(buffer, onEvent)
    }
  } finally {
    // 主动 abort 时也要释放底层连接
    reader.releaseLock()
  }
}

export async function streamDemo({
  text,
  signal,
  onChunk,
}: StreamDemoOptions): Promise<void> {
  const res = await fetch(`/api/v1/demo/stream?text=${encodeURIComponent(text)}`, {
    headers: { Accept: 'text/event-stream' },
    signal,
  })

  if (!res.ok) {
    throw new ApiError(res.status, 'STREAM_FAILED', `流式请求失败（${res.status}）`)
  }

  await readSSE<StreamChunk>(res, onChunk)
}
