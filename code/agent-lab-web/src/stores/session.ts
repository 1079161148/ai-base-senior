import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface SessionInfo {
  id: string
  title: string
  msg_count: number
  /** 会话里最后一次提问。标题不随对话更新，靠它判断这个会话聊到哪了 */
  last_user_message?: string | null
  created_at: string
  updated_at: string
}

const STORAGE_KEY = 'agent-lab:current-session'

export const useSessionStore = defineStore('session', () => {
  // 刷新页面后接着上一次会话，而不是每次都从零开始
  const currentId = ref<string | null>(localStorage.getItem(STORAGE_KEY))
  const sessions = ref<SessionInfo[]>([])
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try {
      const res = await fetch('/api/v1/sessions')
      if (!res.ok) {
        sessions.value = []
        return
      }
      sessions.value = (await res.json()) as SessionInfo[]
    } catch {
      // 后端没起来时不要把页面卡成 loading
      sessions.value = []
    } finally {
      loading.value = false
    }
  }

  function setCurrent(id: string | null) {
    currentId.value = id
    if (id) localStorage.setItem(STORAGE_KEY, id)
    else localStorage.removeItem(STORAGE_KEY)
  }

  async function create(title?: string): Promise<string> {
    const res = await fetch('/api/v1/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title || '' }),
    })
    const data = (await res.json()) as { id: string }
    setCurrent(data.id)
    await fetchAll()
    return data.id
  }

  async function remove(id: string) {
    const res = await fetch(`/api/v1/sessions/${id}`, { method: 'DELETE' })
    // fetch 不会因为 4xx/5xx 抛错，不主动检查的话界面会显示"已删除"但数据还在。
    // 404 当成功处理：目标早就没了，用户的目的（让它消失）已经达到。
    if (!res.ok && res.status !== 404) {
      throw new Error(`删除失败（${res.status}）`)
    }
    if (currentId.value === id) setCurrent(null)
    await fetchAll()
  }

  /**
   * 本地记住的会话可能在别处被删了。
   * 每次进页面校验一次，失效就清掉，避免拿一个不存在的 id 去发消息。
   */
  async function restoreCurrent(): Promise<boolean> {
    const id = currentId.value
    if (!id) return false
    if (!sessions.value.some(s => s.id === id)) {
      setCurrent(null)
      return false
    }
    return true
  }

  return {
    currentId,
    sessions,
    loading,
    fetchAll,
    setCurrent,
    create,
    remove,
    restoreCurrent,
  }
})