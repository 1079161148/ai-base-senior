<script setup lang="ts">
import { computed } from 'vue'
import { NTag, NCollapse, NCollapseItem, NSpace, NButton, NIcon } from 'naive-ui'
import { CopyOutline, RefreshOutline } from '@vicons/ionicons5'
import type { ToolEvent, TraceStep } from '../../api/chat'
import { renderMarkdown, stripMarkdown } from '../../utils/markdown'
import ToolCallCard from './ToolCallCard.vue'

const props = defineProps<{
  role: string
  content: string
  reasoning: string
  reasoningOpen: boolean
  tools: ToolEvent[]
  steps: TraceStep[]
  openSteps: number[]
  isGenerating: boolean
  /** 只有最后一条回答才允许重新生成，见 store 里的说明 */
  canRegenerate: boolean
}>()

const emit = defineEmits<{
  toggleStep: [step: number]
  copy: []
  regenerate: []
}>()

const htmlContent = computed(() => renderMarkdown(props.content))
const hasReasoning = computed(() => props.reasoning.length > 0)

/** 步骤标题只取纯文本，否则会把 **加粗** 这类原始符号直接显示出来 */
function stepTitle(s: TraceStep): string {
  const raw = stripMarkdown(s.model_output || s.reasoning || '[工具调用]')
  const flat = raw.replace(/\s+/g, ' ').trim()
  return `步骤 ${s.step + 1} · ${flat.slice(0, 60)}${flat.length > 60 ? '…' : ''}`
}
</script>

<template>
  <div class="bubble" :class="`bubble--${role}`">
    <!-- 思考过程 -->
    <n-collapse v-if="hasReasoning">
      <n-collapse-item :title="`思考过程 (${reasoning.length} 字)`" :name="'reasoning'">
        <div class="reasoning">{{ reasoning }}</div>
      </n-collapse-item>
    </n-collapse>

    <!-- 正文（Markdown 渲染） -->
    <div v-if="content" class="md-body" v-html="htmlContent" />

    <!-- 生成中光标 -->
    <span v-if="isGenerating && !content" class="cursor-blink">▌</span>

    <!-- 工具调用（生成中） -->
    <n-space v-if="isGenerating && tools.length" :size="4" class="tools-live">
      <ToolCallCard
        v-for="t in tools"
        :key="t.id"
        :tool="t"
        mode="live"
      />
    </n-space>

    <!-- 工具调用追踪（结束后 trace） -->
    <n-collapse v-if="!isGenerating && steps.length">
      <n-collapse-item
        v-for="s in steps"
        :key="s.step"
        :name="String(s.step)"
        :title="stepTitle(s)"
      >
        <template #header-extra>
          <n-tag :bordered="false" size="tiny" type="info">
            {{ s.prompt_tokens + s.completion_tokens }} token · {{ s.duration_ms }}ms
          </n-tag>
        </template>
        <div class="step-model md-body" v-html="renderMarkdown(s.model_output || s.reasoning || '[工具调用]')" />
        <ToolCallCard
          v-for="tc in s.tool_calls"
          :key="tc.name"
          :tool="tc"
          mode="trace"
        />
      </n-collapse-item>
    </n-collapse>

    <!-- 操作栏：只在回答结束后出现，生成中点了也没意义 -->
    <div v-if="role === 'assistant' && !isGenerating && content" class="bubble__actions">
      <n-button text size="tiny" @click="emit('copy')">
        <template #icon><n-icon><CopyOutline /></n-icon></template>
        复制
      </n-button>
      <n-button v-if="canRegenerate" text size="tiny" @click="emit('regenerate')">
        <template #icon><n-icon><RefreshOutline /></n-icon></template>
        重新生成
      </n-button>
    </div>
  </div>
</template>

<style scoped>
.bubble {
  padding: 14px 18px;
  border-radius: 10px;
  line-height: 1.7;
}
.bubble--user {
  background: rgba(45, 212, 191, 0.08);
  border: 1px solid rgba(45, 212, 191, 0.12);
}
.bubble--assistant {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.reasoning {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
  white-space: pre-wrap;
  padding: 8px 0;
}

.step-model {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  padding: 8px 0;
}

.tools-live { margin-top: 8px; }

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #2dd4bf;
}
@keyframes blink { 50% { opacity: 0; } }

.bubble__actions {
  display: flex;
  gap: 12px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  /* 默认半透明，鼠标移上来才清晰 —— 操作栏不该抢正文的注意力 */
  opacity: 0.45;
  transition: opacity 0.15s;
}
.bubble:hover .bubble__actions { opacity: 1; }
</style>