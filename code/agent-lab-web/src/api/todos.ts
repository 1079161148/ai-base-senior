import { request } from './http'

/** 与后端 TodoOut 一一对应 —— 字段名必须是 snake_case，和 Python 保持一致 */
export interface Todo {
  id: number
  title: string
  done: boolean
  created_at: string
}

/** 对应 TodoCreate：只有 title，客户端无法伪造 id / created_at */
export interface TodoCreate {
  title: string
}

/** 对应 TodoUpdate：全部可选，实现 PATCH 局部更新 */
export interface TodoUpdate {
  title?: string
  done?: boolean
}

export const todoApi = {
  list: () => request<Todo[]>('/todos'),

  create: (payload: TodoCreate) =>
    request<Todo>('/todos', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  update: (id: number, payload: TodoUpdate) =>
    request<Todo>(`/todos/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  remove: (id: number) =>
    request<void>(`/todos/${id}`, {
      method: 'DELETE',
    }),
}
