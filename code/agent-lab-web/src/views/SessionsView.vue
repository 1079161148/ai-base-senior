<script setup lang="ts">
import { onMounted, h, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  NDataTable, NButton, NSpace, NResult, NSpin, NInput, NPopconfirm,
  useMessage, type DataTableColumns,
} from 'naive-ui'
import { useSessionStore, type SessionInfo } from '../stores/session'

const session = useSessionStore()
const router = useRouter()
const message = useMessage()

const keyword = ref('')

/**
 * 前端过滤，不请求后端。
 * 原因：list_sessions 最多返回 50 条，一次全拿到本地过滤没有延迟，
 * 也不需要为搜索单独做一个带分页的接口。
 * 如果以后要支持几千条会话，这里必须改成后端分页 + 全文检索。
 */
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return session.sessions
  return session.sessions.filter((s) => {
    const haystack = `${s.title || ''} ${s.last_user_message || ''}`.toLowerCase()
    return haystack.includes(k)
  })
})

/**
 * 打开历史会话。
 * 先把 currentId 指向目标会话，再跳转 —— 顺序反了的话 ChatView 已在挂载时
 * 读到旧的 currentId，就会加载错会话。消息由 ChatView 的 onMounted 统一拉取。
 */
function openSession(id: string) {
  session.setCurrent(id)
  router.push('/')
}

const columns: DataTableColumns<SessionInfo> = [
  {
    title: '标题', key: 'title', minWidth: 150,
    render(r) {
      return h(
        NButton,
        { text: true, onClick: () => openSession(r.id) },
        { default: () => r.title || '新对话' },
      )
    },
  },
  {
    title: '最近提问', key: 'last_user_message', minWidth: 220,
    // 标题只在首轮生成、之后不变，所以必须有这一列，
    // 否则「后来追加的话题」在列表里完全看不出来
    ellipsis: { tooltip: true },
    render(r) {
      const t = (r.last_user_message || '').replace(/\s+/g, ' ').trim()
      if (!t) return '—'
      return t.length > 40 ? `${t.slice(0, 40)}…` : t
    },
  },
  { title: '消息数', key: 'msg_count', width: 80 },
  {
    title: '最后更新', key: 'updated_at', width: 140,
    render(r) { return r.updated_at.slice(0, 16).replace('T', ' ') },
  },
  {
    title: '操作', key: 'actions', width: 80,
    render(r) {
      // 删除不可逆（连消息和记忆一起删），必须二次确认
      return h(
        NPopconfirm,
        { onPositiveClick: () => deleteSession(r.id) },
        {
          trigger: () => h(
            NButton,
            { size: 'tiny', quaternary: true },
            { default: () => '删除' },
          ),
          default: () => `删除会话「${r.title || '新对话'}」？消息和记忆会一起删除，无法恢复。`,
        },
      )
    },
  },
]

async function deleteSession(id: string) {
  try {
    await session.remove(id)
    message.success('已删除')
  } catch {
    message.error('删除失败，请重试')
  }
}

onMounted(() => session.fetchAll())
</script>

<template>
  <div>
    <div class="sess-header">
      <h2>会话管理</h2>
      <NSpace>
        <NInput
          v-model:value="keyword"
          placeholder="搜索标题或提问内容"
          clearable
          size="small"
          style="width: 220px"
        />
        <NButton size="small" quaternary @click="session.fetchAll()">刷新</NButton>
      </NSpace>
    </div>

    <NResult
      v-if="!session.loading && session.sessions.length === 0"
      status="info"
      title="暂无会话"
      description="在对话页面发送消息即自动创建会话"
      size="small"
    />

    <NResult
      v-else-if="!session.loading && filtered.length === 0"
      status="info"
      title="没有匹配的会话"
      :description="`没有标题或提问包含「${keyword}」的会话`"
      size="small"
    />

    <NSpin v-if="session.loading" />

    <NDataTable
      v-if="filtered.length"
      :columns="columns"
      :data="filtered"
      :bordered="false"
      :single-line="false"
      size="small"
      :pagination="{ pageSize: 10 }"
      :scroll-x="720"
      class="sess-table"
    />
  </div>
</template>

<style scoped>
.sess-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.sess-header h2 { margin: 0; font-size: 18px; color: #e2e8f0; }
.sess-table { margin-top: 12px; }
</style>
