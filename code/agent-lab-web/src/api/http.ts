/**
 * 统一请求封装。
 *
 * 后端所有错误都是同一个形状：
 *   { "code": "TODO_NOT_FOUND", "message": "待办 1 不存在", "detail": null }
 * 所以这里把「HTTP 状态码 + JSON 解析 + 错误归一」全部收在一处，
 * 组件里只需要 try/catch 一个 ApiError。
 */

/** 后端错误响应体 */
interface ApiErrorBody {
  code: string
  message: string
  detail: unknown
}

/** 归一化后的异常：UI 直接展示 message，用 code 做分支 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const BASE = '/api/v1'

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response

  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init.headers ?? {}),
      },
    })
  } catch {
    // fetch 只在「网络层」失败时 reject：断网、DNS 失败、被 CORS 拒绝。
    // HTTP 4xx/5xx 不会走到这里 —— 这是新手最常见的误判点。
    throw new ApiError(0, 'NETWORK_ERROR', '网络异常，请确认后端已启动（8001）')
  }

  // 204 没有响应体，不能去 JSON.parse，否则会抛 SyntaxError
  if (res.status === 204 || res.status === 205) {
    return undefined as T
  }

  const text = await res.text()
  let data: unknown = null

  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      throw new ApiError(res.status, 'BAD_RESPONSE', `响应不是合法 JSON（${res.status}）`)
    }
  }

  if (!res.ok) {
    const body = data as ApiErrorBody | null
    throw new ApiError(
      res.status,
      body?.code ?? 'UNKNOWN',
      body?.message ?? `请求失败（${res.status}）`,
    )
  }

  return data as T
}
