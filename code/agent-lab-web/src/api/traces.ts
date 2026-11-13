/**
 * Trace 查询（S2 / S7）。
 *
 * trace 是「那次对话到底发生了什么」的可回放记录：
 * 每一步模型说了什么、调了什么工具、花了多少 token、耗了多久。
 * 排查"为什么这轮特别慢/特别贵"靠的就是它。
 */

import { ApiError } from './http'

/** 列表项：后端只返回摘要，不含 steps，避免一次拉几百 KB */
export interface TraceSummary {
  trace_id: string
  started_at: string
  question: string
  stopped_reason: string
  usage: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
    cost_cny?: number
    tool_calls?: number
    chars?: number
  } | null
}

export interface TraceToolRecord {
  name: string
  arguments: unknown
  result: unknown
  status: string
  duration_ms: number
}

export interface TraceStepRecord {
  step: number
  model_output: string
  reasoning: string
  tool_calls: TraceToolRecord[]
  prompt_tokens: number
  completion_tokens: number
  duration_ms: number
}

/** 完整 trace 的结构与后端 Trace dataclass 一一对应 */
export interface TraceDetail {
  trace_id: string
  started_at: string
  model: string
  question: string
  duration_ms: number
  steps: TraceStepRecord[]
  usage: TraceSummary['usage']
  stopped_reason: string
  session_id: string | null
  config_fingerprint: string
  prompt_version: string
  tool_version: string
  structured: boolean
  structured_attempts: number
}

const BASE = '/api/v1/traces'

async function assertOk(res: Response): Promise<void> {
  if (res.ok) return
  const text = await res.text()
  let code = 'TRACE_FAILED'
  let msg = `请求失败（${res.status}）`
  try {
    const body = JSON.parse(text) as { code?: string; message?: string }
    if (body.code) code = body.code
    if (body.message) msg = body.message
  } catch {
    // 非 JSON 响应，保留默认文案
  }
  throw new ApiError(res.status, code, msg)
}

export async function fetchTraces(limit = 30): Promise<TraceSummary[]> {
  const res = await fetch(`${BASE}?limit=${limit}`)
  await assertOk(res)
  return (await res.json()) as TraceSummary[]
}

export async function fetchTrace(id: string): Promise<TraceDetail> {
  const res = await fetch(`${BASE}/${encodeURIComponent(id)}`)
  await assertOk(res)
  return (await res.json()) as TraceDetail
}
