<script setup lang="ts">
import { ref, nextTick, watch, onMounted, computed } from 'vue'
import {
  NInput, NButton, NSpace, NScrollbar, NTag, NProgress,
  NSkeleton, NResult, NAlert, NUpload,
  useMessage, type UploadFileInfo,
} from 'naive-ui'
import { useChatStore, type Message } from '../stores/chat'
import { useSessionStore } from '../stores/session'
import MessageBubble from '../components/chat/MessageBubble.vue'

const chat = useChatStore()
const session = useSessionStore()
const message = useMessage()

const draft = ref('')
const scrollEl = ref<InstanceType<typeof NScrollbar> | null>(null)
const userScrolledUp = ref(false)

const canSend = computed(() => !chat.running && draft.value.trim().length > 0)

// ---- 滚动控制：用户上滑暂停自动滚动 ----
function autoScroll() {
  if (userScrolledUp.value) return
  nextTick(() => {
    scrollEl.value?.scrollTo({ top: 999999, behavior: 'smooth' })
  })
}

function onScroll(e: Event) {
  const el = (e.target as HTMLElement)
  const dist = el.scrollHeight - el.scrollTop - el.clientHeight
  userScrolledUp.value = dist > 80
}

watch(() => chat.messages.length, autoScroll)
watch(() => chat.lastMessage?.content, autoScroll)

// ---- 发送 ----
// 键盘处理必须写成一个普通函数。
// 直接写两个 @keydown.enter / @keydown.shift.enter 时，Vue 会把它们合并成
// 数组塞进组件的 onKeydown prop，Naive UI 的 NInput 只接受单个函数，会告警。
function onInputKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter' || e.shiftKey) return
  e.preventDefault()
  handleSend()
}

async function handleSend() {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  userScrolledUp.value = false
  await chat.send(text)
  autoScroll()
}

// ---- 文档上传 ----
const uploadMsg = ref('')
const uploading = ref(false)

async function handleUpload({ file }: { file: UploadFileInfo }) {
  if (!file.file) return
  uploading.value = true
  uploadMsg.value = ''
  try {
    const form = new FormData()
    form.append('file', file.file)
    const resp = await fetch('/api/v1/rag/upload', { method: 'POST', body: form })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error((err as { message?: string }).message || `HTTP ${resp.status}`)
    }
    const data = await resp.json() as { chunks?: number; title?: string }
    uploadMsg.value = `已索引 ${data.chunks ?? 0} 个片段`
    message.success(`《${data.title ?? file.name}》已索引`)
  } catch (e) {
    uploadMsg.value = '上传失败'
    message.error(e instanceof Error ? e.message : '未知错误')
  } finally { uploading.value = false }
}

// ---- 会话管理 ----
/**
 * 开新对话：只清空界面并把 currentId 置空。
 * 不预先 POST /sessions —— 那样会留下一堆没有消息的空会话。
 * 后端在收到第一条消息且 session_id 为 null 时会自动建会话并回传 id。
 */
function newSession() {
  if (chat.running) chat.stop()
  chat.clear()
  session.setCurrent(null)
  draft.value = ''
  userScrolledUp.value = false
}

// 进页面时恢复上次会话；本地记住的 id 若已被删除则忽略
onMounted(async () => {
  await session.fetchAll()

  // 正在生成时不要重新拉历史：loadSession 会整体替换 messages，
  // 那个正在流式写入的气泡（以及它的响应式代理）就丢了。
  // 换句话说，切到「文档」再切回来，回答应该继续往下写，而不是被打断。
  if (chat.running) {
    autoScroll()
    return
  }

  const valid = await session.restoreCurrent()
  if (!valid) return
  try {
    await chat.loadSession(session.currentId!)
    autoScroll()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '加载会话失败')
    session.setCurrent(null)
  }
})

// 注意：这里**不能**在 onBeforeUnmount 里 stop()。
// chat 是全局 Pinia store，流不归这个组件所有；
// 切换菜单时组件卸载就 abort，会让「切个菜单回来发现回答停了」。

// ---- 消息操作 ----
/** 最后一条 assistant 的 id：只有它能重新生成（服务端是追加语义，见 store） */
const lastAssistantId = computed(() => {
  for (let i = chat.messages.length - 1; i >= 0; i--) {
    const m = chat.messages[i]!
    if (m.role === 'assistant') return m.id
  }
  return -1
})

/**
 * 复制的是 Markdown 原文，不是渲染后的纯文本。
 * 用户复制回答大多是为了贴到别处继续用，保留代码块和列表结构更有价值。
 */
async function copyMessage(m: Message) {
  try {
    await navigator.clipboard.writeText(m.content)
    message.success('已复制')
  } catch {
    // 非安全上下文（http + 非 localhost）或用户拒绝授权时 clipboard 不可用
    message.warning('浏览器不允许自动复制，请手动选中')
  }
}

async function regenerateMessage(m: Message) {
  const ok = await chat.regenerate(m.id)
  if (!ok) {
    // 只有"最后一条"能重新生成，其它情况（生成中 / 不是最后一条）统一提示
    message.info(chat.running ? '正在生成，请稍候' : '只能重新生成最后一条回答')
  }
}

// ---- 示例问题 ----
const examples = ['帮我列出所有待办', '接口超时怎么处理？', '什么是 RRF？']
</script>

<template>
  <div class="chat-view">
    <!-- 顶部工具栏 -->
    <div class="chat-toolbar">
      <NSpace align="center">
        <span class="chat-title">agent-lab · 对话</span>
        <NTag v-if="session.currentId" type="info" size="small" :bordered="false">
          会话 {{ session.currentId?.slice(0, 8) }}
        </NTag>
      </NSpace>
      <NSpace>
        <NButton size="small" quaternary @click="newSession">
          + 新对话
        </NButton>
      </NSpace>
    </div>

    <!-- 消息列表 -->
    <NScrollbar
      ref="scrollEl"
      class="msg-list"
      :style="{ flex: 1 }"
      @scroll="onScroll"
    >
      <!-- 空状态 -->
      <NResult
        v-if="chat.messages.length === 0 && !chat.running"
        status="info"
        title="开始对话"
        description="问任何关于待办或文档的问题"
        size="small"
      >
        <template #footer>
          <NSpace vertical>
            <NButton
              v-for="ex in examples"
              :key="ex"
              quaternary
              size="small"
              @click="draft = ex; handleSend()"
            >
              {{ ex }}
            </NButton>
          </NSpace>
        </template>
      </NResult>

      <!-- 骨架屏（首次加载） -->
      <NSkeleton v-if="chat.running && chat.messages.length === 0" text :repeat="3" />

      <!-- 消息列表 -->
      <div v-for="m in chat.messages" :key="m.id" class="msg-wrapper">
        <MessageBubble
          :role="(m.role as string)"
          :content="m.content"
          :reasoning="m.reasoning"
          :reasoning-open="m.reasoningOpen"
          :tools="m.tools"
          :steps="m.trace?.steps ?? []"
          :open-steps="[]"
          :is-generating="chat.running && m.id === chat.lastMessage?.id"
          :can-regenerate="!chat.running && m.id === lastAssistantId"
          @copy="copyMessage(m)"
          @regenerate="regenerateMessage(m)"
        />

        <!-- 上下文预算 -->
        <div v-if="m.contextUsage" class="budget-bar">
          <NProgress
            type="line"
            :percentage="Math.round(m.contextUsage.ratio * 100)"
            :color="m.contextUsage.ratio > 0.8 ? '#ef4444' : m.contextUsage.ratio > 0.6 ? '#fbbf24' : '#2dd4bf'"
            :height="4"
            :border-radius="2"
            :show-indicator="false"
          />
          <span class="budget-text">
            {{ m.contextUsage.used_tokens }} / {{ m.contextUsage.budget_tokens }} token
          </span>
        </div>
      </div>

      <!-- 错误提示 -->
      <NAlert
        v-if="chat.error"
        type="error"
        :title="chat.error"
        closable
        class="error-alert"
        @close="chat.error = ''"
      />
    </NScrollbar>

    <!-- 底部输入区 -->
    <div class="input-area">
      <!-- 上传区域 -->
      <div v-if="uploadMsg" class="upload-status">
        <NTag :bordered="false" type="info" size="small">{{ uploadMsg }}</NTag>
      </div>

      <NSpace vertical :size="8" style="width: 100%">
        <NInput
          v-model:value="draft"
          type="textarea"
          placeholder="输入问题…"
          :autosize="{ minRows: 1, maxRows: 5 }"
          :disabled="chat.running"
          @keydown="onInputKeydown"
        />
        <NSpace justify="end">
          <NUpload
            :show-file-list="false"
            accept=".md,.txt,.pdf"
            :disabled="uploading"
            @change="handleUpload"
          >
            <NButton size="small" quaternary :loading="uploading">
              📁 上传文档
            </NButton>
          </NUpload>
          <NButton
            v-if="!chat.running"
            type="primary"
            :disabled="!canSend"
            @click="handleSend"
          >
            发送
          </NButton>
          <NButton
            v-else
            type="warning"
            @click="chat.stop()"
          >
            停止生成
          </NButton>
        </NSpace>
      </NSpace>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 48px);
}

/* 移动端顶部多了一条 56px 的浮动按钮避让区，高度要跟着减，否则输入框会被顶出屏幕 */
@media (max-width: 768px) {
  .chat-view {
    height: calc(100vh - 84px);
  }
  .chat-title {
    font-size: 13px;
  }
}
.chat-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  margin-bottom: 12px;
}
.chat-title {
  font-size: 20px; font-weight: 700;
  color: #2dd4bf;
}
.msg-list {
  padding: 8px 0;
}
.msg-wrapper {
  margin-bottom: 16px;
}
.budget-bar {
  margin-top: 6px; display: flex; align-items: center; gap: 10px;
}
.budget-text {
  font-size: 11px; color: rgba(255,255,255,0.35); white-space: nowrap;
}
.input-area {
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.upload-status { margin-bottom: 4px; }
.error-alert { margin: 8px 0; }
</style>