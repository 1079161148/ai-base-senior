/** S7 · 指标接口。看板只读这两个端点。 */

import { request } from './http'

export interface DayStat {
  date: string
  requests: number
  success_rate: number
  p95_ms: number
  cost_cny: number
}

export interface FingerprintStat {
  fingerprint: string
  model: string
  requests: number
  success_rate: number
  avg_cost_cny: number
}

export interface MetricsSummary {
  window_days: number
  requests: number
  success_rate: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
  avg_duration_ms: number
  avg_cost_cny: number
  total_cost_cny: number
  total_tool_calls: number
  by_status: Record<string, number>
  by_day: DayStat[]
  by_fingerprint: FingerprintStat[]
}

export interface FailureRow {
  trace_id: string
  question: string
  status: string
  model: string
  duration_ms: number
  cost_cny: number
  started_at: string
}

export function fetchSummary(days = 7) {
  return request<MetricsSummary>(`/metrics/summary?days=${days}`)
}

export function fetchFailures(limit = 20) {
  return request<FailureRow[]>(`/metrics/failures?limit=${limit}`)
}
