/**
 * S9 · 鉴权：token 存取 + 登录/注册 + 全局 fetch 拦截。
 *
 * **为什么要在 window.fetch 上做一层，而不是逐个调用点加 header**：
 * 项目里有十几处裸 fetch（SSE 流、FormData 上传、会话增删改）。
 * 一个个改，漏掉一处就是一个 401 —— 而且漏掉的地方往往是最难测的
 * （比如上传大文件、或者流式对话）。
 *
 * 只拦截 `/api/` 开头的请求，静态资源和外部链接不受影响。
 */

import { ApiError } from './http'

const TOKEN_KEY = 'agent-lab:token'
const USER_KEY = 'agent-lab:user'

export interface AuthUser {
  id: string
  username: string
  display_name: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

// ---------------------------------------------------------------- 本地存储

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    // 存的东西坏了就当没登录，不要让首页白屏
    return null
  }
}

export function saveAuth(result: LoginResult): void {
  localStorage.setItem(TOKEN_KEY, result.access_token)
  localStorage.setItem(USER_KEY, JSON.stringify(result.user))
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isLoggedIn(): boolean {
  return getToken().length > 0
}

// ---------------------------------------------------------------- 接口

/** 登录 / 注册不需要带旧 token，401 也不该触发跳转 */
function isAuthEndpoint(url: string): boolean {
  return url.includes('/api/v1/auth/')
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const text = await res.text()
  const data = text ? (JSON.parse(text) as unknown) : null

  if (!res.ok) {
    const err = data as { code?: string; message?: string } | null
    throw new ApiError(res.status, err?.code ?? 'AUTH_FAILED', err?.message ?? '请求失败')
  }
  return data as T
}

export function login(username: string, password: string): Promise<LoginResult> {
  return postJson<LoginResult>('/auth/login', { username, password })
}

export function register(
  username: string,
  password: string,
  displayName = '',
): Promise<LoginResult> {
  return postJson<LoginResult>('/auth/register', {
    username,
    password,
    display_name: displayName,
  })
}

// ---------------------------------------------------------------- 全局拦截

let installed = false

export function installAuthFetch(): void {
  if (installed) return
  installed = true

  const original = window.fetch.bind(window)

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    // 只处理字符串 URL：本项目的请求全部是字符串形式，
    // Request 对象在这里重建代价大且容易丢属性。
    const url = typeof input === 'string' ? input : input.toString()

    if (url.includes('/api/') && !isAuthEndpoint(url)) {
      const token = getToken()
      if (token) {
        const headers = new Headers(init?.headers)
        // 不覆盖调用方自己设的 Authorization（脚本/测试可能手动指定）
        if (!headers.has('Authorization')) {
          headers.set('Authorization', `Bearer ${token}`)
        }
        init = { ...(init ?? {}), headers }
      }
    }

    const res = await original(input, init)

    // 401 统一处理：token 过期、被改、用户被删，都走这里。
    // 不能只在个别页面处理 —— 否则用户在某个页面会一直看到空数据。
    if (res.status === 401 && !isAuthEndpoint(url)) {
      clearAuth()
      if (!window.location.pathname.startsWith('/login')) {
        const back = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.assign(`/login?redirect=${back}`)
      }
    }

    return res
  }
}
