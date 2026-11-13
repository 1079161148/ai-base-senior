<script setup lang="ts">
/**
 * Trace 回放页。
 *
 * 解决的问题很具体：指标页告诉你「P95 从 3s 涨到 8s」，
 * 但为什么涨，只能靠 trace 一步步看。
 *
 * 所以这一页只做三件事：找得到（列表 + 搜索）、看得清（每步耗时/token）、
 * 能定位（配置指纹 + 停止原因）。
 */
import { computed, onMounted, ref } from 'vue'
import {
  NButton, NEmpty, NInput, NSpin, NTag, NAlert,
  useMessage,
} from 'naive-ui'
import { renderMarkdown } from '../utils/markdown'
import {
  fetchTrace, fetchTraces,
  type TraceDetail, type TraceSummary,
} from '../api/traces'
import { ApiError } from '../api/http'

const message = useMessage()

const list = ref<TraceSummary[]>([])
const listLoading = ref(false)
const detail = ref<TraceDetail | null>(null)
const detailLoading = ref(false)
const keyword = ref('')

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return list.value
  return list.value.filter(t =>
    `${t.question || ''} ${t.trace_id || ''}`.toLowerCase().includes(k),
  )
})

/** 停止原因不是 completed 的，都在界面上标出来 —— 那些才是排查重点 */
const STOP_TYPE: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  completed: 'success',
  stopped_by_user: 'warning',
  max_steps: 'warning',
  tool_timeout: 'error',
  llm_error: 'error',
}

function stopLabel(reason: string): string {
  return reason || 'completed'
}

function ms(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${Math.round(v)}ms`
}

function money(v?: number): string {
  return `¥${(v ?? 0).toFixed(6)}`
}

async function loadList() {
  listLoading.value = true
  try {
    list.value = await fetchTraces(30)
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : '加载 trace 列表失败')
  } finally {
    listLoading.value = false
  }
}

async function select(id: string) {
  detailLoading.value = true
  try {
    detail.value = await fetchTrace(id)
  } catch (e) {
    detail.value = null
    message.error(e instanceof ApiError ? e.message : '加载 trace 失败')
  } finally {
    detailLoading.value = false
  }
}

onMounted(async () => {
  await loadList()
  // 默认打开最新一条：绝大多数时候用户进来就是想看"刚才那次"
  if (list.value.length > 0) void select(list.value[0]!.trace_id)
})
</script>

<template>
  <div class="tr">
    <header class="tr__head">
      <div>
        <h1>Trace 回放</h1>
        <p class="tr__hint">
          Agent 每一步的可回放记录。回答变慢、变贵、工具出错，都在这里找原因。
        </p>
      </div>
      <n-button size="small" quaternary :loading="listLoading" @click="loadList">刷新</n-button>
    </header>

    <div class="tr__body">
      <aside class="tr__list">
        <n-input
          v-model:value="keyword"
          size="small"
          clearable
          placeholder="搜索问题或 trace id"
          class="tr__search"
        />
        <n-spin v-if="listLoading" size="small" />
        <n-empty v-else-if="filtered.length === 0" size="small" description="没有 trace 记录" />
        <button
          v-for="t in filtered"
          :key="t.trace_id"
          class="tr__item"
          :class="{ 'tr__item--active': detail?.trace_id === t.trace_id }"
          @click="select(t.trace_id)"
        >
          <div class="tr__item-q">{{ t.question || '(空问题)' }}</div>
          <div class="tr__item-meta">
            <span>{{ (t.started_at || '').slice(5, 16).replace('T', ' ') }}</span>
            <n-tag
              size="tiny"
              :bordered="false"
              :type="STOP_TYPE[stopLabel(t.stopped_reason)] || 'default'"
            >
              {{ stopLabel(t.stopped_reason) }}
            </n-tag>
          </div>
        </button>
      </aside>

      <section class="tr__detail">
        <n-spin v-if="detailLoading" />
        <n-empty v-else-if="!detail" description="左侧选择一条 trace" />

        <template v-else>
          <div class="tr__q">{{ detail.question }}</div>

          <div class="tr__stats">
            <div class="stat">
              <div class="stat__k">总耗时</div>
              <div class="stat__v">{{ ms(detail.duration_ms) }}</div>
            </div>
            <div class="stat">
              <div class="stat__k">token</div>
              <div class="stat__v">
                {{ detail.usage?.prompt_tokens ?? 0 }} + {{ detail.usage?.completion_tokens ?? 0 }}
              </div>
            </div>
            <div class="stat">
              <div class="stat__k">成本</div>
              <div class="stat__v">{{ money(detail.usage?.cost_cny) }}</div>
            </div>
            <div class="stat">
              <div class="stat__k">工具调用</div>
              <div class="stat__v">{{ detail.usage?.tool_calls ?? 0 }}</div>
            </div>
            <div class="stat">
              <div class="stat__k">步数</div>
              <div class="stat__v">{{ detail.steps.length }}</div>
            </div>
          </div>

          <div class="tr__tags">
            <n-tag size="tiny" :bordered="false">模型 {{ detail.model }}</n-tag>
            <n-tag size="tiny" :bordered="false">指纹 {{ detail.config_fingerprint }}</n-tag>
            <n-tag size="tiny" :bordered="false">提示词 {{ detail.prompt_version }}</n-tag>
            <n-tag size="tiny" :bordered="false">工具 {{ detail.tool_version }}</n-tag>
            <n-tag
              v-if="detail.structured"
              size="tiny"
              type="info"
              :bordered="false"
            >
              结构化 · 尝试 {{ detail.structured_attempts }} 次
            </n-tag>
            <n-tag v-if="detail.session_id" size="tiny" :bordered="false">
              会话 {{ detail.session_id.slice(0, 8) }}
            </n-tag>
          </div>

          <n-alert
            v-if="stopLabel(detail.stopped_reason) !== 'completed'"
            type="warning"
            :bordered="false"
            class="tr__stop"
          >
            这次没有正常结束：{{ stopLabel(detail.stopped_reason) }}
          </n-alert>

          <!-- 步骤 -->
          <div
            v-for="s in detail.steps"
            :key="s.step"
            class="step"
          >
            <div class="step__head">
              <span class="step__no">步骤 {{ s.step + 1 }}</span>
              <span class="step__cost">
                {{ s.prompt_tokens + s.completion_tokens }} token · {{ ms(s.duration_ms) }}
              </span>
            </div>

            <div
              v-if="s.model_output"
              class="md-body step__body"
              v-html="renderMarkdown(s.model_output)"
            />

            <details v-if="s.reasoning" class="step__reasoning">
              <summary>思考过程（{{ s.reasoning.length }} 字）</summary>
              <div class="step__reasoning-body">{{ s.reasoning }}</div>
            </details>

            <div
              v-for="(tc, i) in s.tool_calls"
              :key="`${tc.name}-${i}`"
              class="tool"
            >
              <div class="tool__head">
                <n-tag
                  size="tiny"
                  :bordered="false"
                  :type="tc.status === 'error' ? 'error' : 'success'"
                >
                  {{ tc.name }}
                </n-tag>
                <span class="tool__ms">{{ ms(tc.duration_ms) }}</span>
              </div>
              <pre class="tool__json">参数 {{ JSON.stringify(tc.arguments, null, 2) }}</pre>
              <pre class="tool__json">结果 {{ JSON.stringify(tc.result, null, 2) }}</pre>
            </div>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tr { display: flex; flex-direction: column; height: 100%; }

.tr__head {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 16px;
}
.tr__head h1 { margin: 0 0 4px; font-size: 20px; color: #2dd4bf; }
.tr__hint { margin: 0; font-size: 12px; color: rgba(255, 255, 255, 0.4); }

.tr__body { display: flex; gap: 20px; flex: 1; min-height: 0; }

.tr__list {
  width: 280px; flex: none;
  overflow-y: auto;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  padding-right: 12px;
}
.tr__search { margin-bottom: 10px; }

.tr__item {
  display: block; width: 100%; text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 6px;
  cursor: pointer;
  color: inherit;
}
.tr__item:hover { background: rgba(255, 255, 255, 0.04); }
.tr__item--active {
  background: rgba(45, 212, 191, 0.08);
  border-color: rgba(45, 212, 191, 0.25);
}
.tr__item-q {
  font-size: 13px; color: #e2e8f0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tr__item-meta {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 6px; font-size: 11px; color: rgba(255, 255, 255, 0.35);
}

.tr__detail { flex: 1; min-width: 0; overflow-y: auto; }
.tr__q {
  font-size: 16px; font-weight: 600; color: #e2e8f0;
  margin-bottom: 14px;
}

.tr__stats {
  display: grid; grid-template-columns: repeat(5, 1fr);
  gap: 10px; margin-bottom: 14px;
}
.stat {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px; padding: 10px 12px;
}
.stat__k { font-size: 11px; color: rgba(255, 255, 255, 0.4); margin-bottom: 4px; }
.stat__v { font-size: 16px; font-weight: 600; color: #e6edf3; }

.tr__tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.tr__stop { margin-bottom: 14px; }

.step {
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.step__head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 8px;
}
.step__no { font-size: 13px; font-weight: 600; color: #2dd4bf; }
.step__cost { font-size: 11px; color: rgba(255, 255, 255, 0.4); }
.step__body { font-size: 13px; color: rgba(255, 255, 255, 0.8); }

.step__reasoning {
  margin-top: 8px; font-size: 12px; color: rgba(255, 255, 255, 0.45);
}
.step__reasoning summary { cursor: pointer; }
.step__reasoning-body {
  margin-top: 6px; white-space: pre-wrap;
  max-height: 240px; overflow-y: auto;
  padding: 8px; background: rgba(0, 0, 0, 0.2); border-radius: 6px;
}

.tool { margin-top: 10px; }
.tool__head { display: flex; align-items: center; gap: 8px; }
.tool__ms { font-size: 11px; color: rgba(255, 255, 255, 0.35); }
/* 窄屏：左右分栏改成上下堆叠，否则列表只剩 100px 宽 */
@media (max-width: 900px) {
  .tr__body { flex-direction: column; }
  .tr__list {
    width: 100%;
    max-height: 220px;
    border-right: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    padding-right: 0;
    padding-bottom: 10px;
  }
  .tr__stats { grid-template-columns: repeat(2, 1fr); }
}

.tool__json {
  margin: 6px 0 0; padding: 8px 10px;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 6px;
  font-size: 12px; line-height: 1.55;
  color: rgba(255, 255, 255, 0.6);
  white-space: pre-wrap; word-break: break-all;
  max-height: 200px; overflow-y: auto;
}
</style>
