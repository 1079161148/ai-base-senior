<script setup lang="ts">
import { NTag } from 'naive-ui'
import { CodeSlashOutline } from '@vicons/ionicons5'
import type { ToolEvent, TraceTool } from '../../api/chat'

const props = defineProps<{
  tool: ToolEvent | TraceTool
  /** 展示模式：live=实时 capsule，trace=可展开卡片 */
  mode: 'live' | 'trace'
}>()


function formatResult(value: unknown): string {
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}
</script>

<template>
  <n-tag
    v-if="mode === 'live'"
    :bordered="false"
    :type="tool.status === 'error' ? 'error' : tool.status === 'done' ? 'success' : 'info'"
    size="small"
  >
    {{ tool.name }}
    <template #icon>
      <n-icon><CodeSlashOutline /></n-icon>
    </template>
  </n-tag>

  <n-card
    v-else
    size="small"
    :title="tool.name"
    :bordered="true"
    class="tool-card"
  >
    <template #header-extra>
      <n-tag
        :bordered="false"
        size="tiny"
        :type="tool.status === 'error' ? 'error' : 'success'"
      >
        {{ tool.status }}
        <template v-if="'duration_ms' in tool">
          · {{ tool.duration_ms }}ms
        </template>
      </n-tag>
    </template>
    <pre class="tool-result">{{ formatResult('result' in tool ? tool.result : null) }}</pre>
  </n-card>
</template>

<style scoped>
.tool-card { margin-bottom: 8px; }
.tool-result {
  margin: 0; padding: 8px;
  background: rgba(255,255,255,0.04);
  border-radius: 6px;
  font-size: 12px; line-height: 1.5;
  max-height: 200px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-all;
  color: rgba(255,255,255,0.6);
}
</style>