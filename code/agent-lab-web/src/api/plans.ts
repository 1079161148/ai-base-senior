/**
 * S6 · 任务计划接口。
 *
 * 计划是**数据**，所以这里的类型全部对应数据库里的行，
 * 而不是某次对话的消息 —— 这样才能编辑、暂停、恢复。
 */

import { request } from './http'

export type PlanStatus =
  | 'pending'
  | 'running'
  | 'awaiting_approval'
  | 'done'
  | 'failed'
  | 'cancelled'

export type StepStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'failed'
  | 'skipped'

export interface PlanStep {
  idx: number
  action: string
  params: Record<string, unknown>
  description: string
  status: StepStatus
  requires_human: boolean
  approved: boolean
  result: unknown
  error: string | null
  attempts: number
  duration_ms: number | null
  finished_at: string | null
}

export interface Plan {
  id: string
  session_id: string | null
  goal: string
  status: PlanStatus
  created_at: string
  updated_at: string
  steps: PlanStep[]
  /** 结构化输出的重试次数：>1 说明模型第一次没守住 schema，值得看一眼 */
  structured_attempts?: number
}

export interface PlanSummary {
  id: string
  goal: string
  status: PlanStatus
  created_at: string
  updated_at: string
  counts?: Record<string, number>
}

export function createPlan(goal: string, sessionId?: string | null) {
  return request<Plan>('/plans', {
    method: 'POST',
    body: JSON.stringify({ goal, session_id: sessionId ?? null }),
  })
}

export function listPlans(limit = 30) {
  return request<PlanSummary[]>(`/plans?limit=${limit}`)
}

export function getPlan(id: string) {
  return request<Plan>(`/plans/${id}`)
}

/** 同步执行：一直等到跑完或需要审批才返回（脚本/测试用） */
export function runPlan(id: string) {
  return request<Plan>(`/plans/${id}/run`, { method: 'POST' })
}

/**
 * 异步执行：立刻返回 accepted，进度靠轮询 getPlan。
 *
 * 前端用这个而不是同步接口：一个 12 步的计划每步几秒，
 * 同步请求会挂住 HTTP 连接，前面的网关多半先超时 ——
 * 用户看到"请求失败"，可实际上后台还在改数据。
 */
export function runPlanAsync(id: string) {
  return request<{ accepted: boolean; reason?: string; plan_id?: string }>(
    `/plans/${id}/run-async`,
    { method: 'POST' },
  )
}

export function approveStep(id: string, idx: number) {
  return request<Plan>(`/plans/${id}/steps/${idx}/approve`, { method: 'POST' })
}

export function patchStep(
  id: string,
  idx: number,
  params: Record<string, unknown>,
) {
  return request<Plan>(`/plans/${id}/steps/${idx}`, {
    method: 'PATCH',
    body: JSON.stringify({ params }),
  })
}

export function cancelPlan(id: string) {
  return request<Plan>(`/plans/${id}/cancel`, { method: 'POST' })
}
