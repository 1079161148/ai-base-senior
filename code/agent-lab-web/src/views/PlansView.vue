<script setup lang="ts">
/**
 * S6 · 计划面板。
 *
 * 三个能力缺一不可：
 *   1. 看见 —— 每一步在做什么、到哪一步了
 *   2. 改 —— 执行前可以改参数（比如删错 id 了）
 *   3. 卡住 —— 高危步骤必须点「确认执行」才往下走
 */
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NEmpty,
  NInput,
  NSpin,
  NTag,
  useMessage,
} from 'naive-ui'
import {
  approveStep,
  cancelPlan,
  createPlan,
  getPlan,
  listPlans,
  patchStep,
  runPlanAsync,
  type Plan,
  type PlanStatus,
  type PlanSummary,
  type StepStatus,
} from '../api/plans'
import { ApiError } from '../api/http'

const message = useMessage()

const goal = ref('')
const creating = ref(false)
const running = ref(false)
const plans = ref<PlanSummary[]>([])
const current = ref<Plan | null>(null)
/** 正在编辑的步骤序号 → 输入框里的 JSON 文本 */
const editing = ref<Record<number, string>>({})

const PLAN_LABEL: Record<PlanStatus, string> = {
  pending: '待执行',
  running: '执行中',
  awaiting_approval: '等待确认',
  done: '已完成',
  failed: '有失败步骤',
  cancelled: '已取消',
}

const PLAN_TYPE: Record<PlanStatus, 'default' | 'info' | 'warning' | 'success' | 'error'> = {
  pending: 'default',
  running: 'info',
  awaiting_approval: 'warning',
  done: 'success',
  failed: 'error',
  cancelled: 'default',
}

const STEP_LABEL: Record<StepStatus, string> = {
  pending: '未执行',
  running: '执行中',
  done: '成功',
  failed: '失败',
  skipped: '已跳过',
}

const STEP_TYPE: Record<StepStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
  pending: 'default',
  running: 'info',
  done: 'success',
  failed: 'error',
  skipped: 'warning',
}

const canRun = computed(() => {
  const p = current.value
  if (!p) return false
  return !['done', 'cancelled', 'running'].includes(p.status)
})

function fail(e: unknown) {
  message.error(e instanceof ApiError ? e.message : '操作失败，请重试')
}

async function refresh() {
  try {
    plans.value = await listPlans()
  } catch (e) {
    fail(e)
  }
}

async function select(id: string) {
  try {
    current.value = await getPlan(id)
    editing.value = {}
  } catch (e) {
    fail(e)
  }
}

async function generate() {
  const text = goal.value.trim()
  if (!text || creating.value) return
  creating.value = true
  try {
    const plan = await createPlan(text)
    current.value = plan
    goal.value = ''
    await refresh()
    if ((plan.structured_attempts ?? 1) > 1) {
      message.info(`模型第 ${plan.structured_attempts} 次才输出合法结构，已自动修复`)
    }
  } catch (e) {
    fail(e)
  } finally {
    creating.value = false
  }
}

/** 轮询间隔：任务在后台跑，前端只负责"看一眼进度"。1 秒足够，不会打出压力。 */
const POLL_MS = 1000
/** 最多轮询 3 分钟：再久就说明后端卡住了，继续等只会让用户干耗 */
const POLL_MAX_TICKS = 180

let pollTimer: number | null = null

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

/**
 * 执行计划：发异步请求 + 轮询状态。
 *
 * 不用同步 `/run`：长计划会把 HTTP 连接挂几十秒，网关早就超时了，
 * 用户看到失败但后台其实还在跑 —— 这种"看起来失败了其实成功了"
 * 是最难解释的状态。
 */
async function doRun() {
  if (!current.value || running.value) return
  running.value = true

  const planId = current.value.id
  try {
    await runPlanAsync(planId)
    await refresh()

    // 轮询到不再 running 为止（可能是 awaiting_approval / done / failed）
    let ticks = 0
    await new Promise<void>((resolve) => {
      pollTimer = window.setInterval(async () => {
        ticks += 1
        try {
          const latest = await getPlan(planId)
          current.value = latest
          if (latest.status !== 'running' || ticks >= POLL_MAX_TICKS) {
            stopPolling()
            resolve()
          }
        } catch {
          // 单次轮询失败不终止：可能只是网络抖了一下
          if (ticks >= POLL_MAX_TICKS) {
            stopPolling()
            resolve()
          }
        }
      }, POLL_MS)
    })

    await refresh()
    if (current.value?.status === 'awaiting_approval') {
      message.warning('有高危步骤，需要你确认后才会继续')
    } else if (ticks >= POLL_MAX_TICKS) {
      message.warning('执行时间过长，已停止轮询。请刷新查看最新状态')
    }
  } catch (e) {
    fail(e)
  } finally {
    stopPolling()
    running.value = false
  }
}

async function doApprove(idx: number) {
  if (!current.value) return
  try {
    current.value = await approveStep(current.value.id, idx)
    message.success('已确认，可以继续执行')
  } catch (e) {
    fail(e)
  }
}

function startEdit(idx: number, params: Record<string, unknown>) {
  editing.value[idx] = JSON.stringify(params, null, 2)
}

function cancelEdit(idx: number) {
  delete editing.value[idx]
}

async function saveEdit(idx: number) {
  if (!current.value) return
  const text = editing.value[idx]
  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(text) as Record<string, unknown>
  } catch {
    message.error('参数必须是合法 JSON')
    return
  }
  try {
    current.value = await patchStep(current.value.id, idx, parsed)
    delete editing.value[idx]
    message.success('参数已更新')
  } catch (e) {
    fail(e)
  }
}

async function doCancel() {
  if (!current.value) return
  try {
    current.value = await cancelPlan(current.value.id)
    await refresh()
  } catch (e) {
    fail(e)
  }
}

function resultText(result: unknown): string {
  if (result === null || result === undefined) return ''
  const s = typeof result === 'string' ? result : JSON.stringify(result, null, 2)
  return s.length > 320 ? `${s.slice(0, 320)}…` : s
}

onMounted(refresh)
</script>

<template>
  <div class="plans">
    <header class="plans__head">
      <div>
        <h1>任务计划</h1>
        <p class="plans__hint">
          把目标拆成可执行步骤。计划是数据，不是对话 —— 可暂停、可改参数、可恢复。
        </p>
      </div>
    </header>

    <div class="plans__compose">
      <n-input
        v-model:value="goal"
        placeholder="例如：把未完成的待办列出来，删掉标题含「测试」的那一条"
        :disabled="creating"
        @keydown.enter.prevent="generate"
      />
      <n-button type="primary" :loading="creating" @click="generate">拆解计划</n-button>
    </div>

    <div class="plans__body">
      <aside class="plans__list">
        <div class="plans__list-title">最近计划</div>
        <n-empty v-if="plans.length === 0" size="small" description="还没有计划" />
        <button
          v-for="p in plans"
          :key="p.id"
          class="plans__item"
          :class="{ 'plans__item--active': current?.id === p.id }"
          @click="select(p.id)"
        >
          <span class="plans__item-goal">{{ p.goal }}</span>
          <n-tag size="tiny" :type="PLAN_TYPE[p.status]">{{ PLAN_LABEL[p.status] }}</n-tag>
        </button>
      </aside>

      <section class="plans__detail">
        <n-empty v-if="!current" description="左侧选择一个计划，或先拆解一个新目标" />

        <template v-else>
          <div class="plans__meta">
            <div>
              <div class="plans__goal">{{ current.goal }}</div>
              <div class="plans__id">{{ current.id }}</div>
            </div>
            <div class="plans__actions">
              <n-tag :type="PLAN_TYPE[current.status]">{{ PLAN_LABEL[current.status] }}</n-tag>
              <n-button size="small" type="primary" :disabled="!canRun" :loading="running" @click="doRun">
                继续执行
              </n-button>
              <n-button size="small" quaternary :disabled="current.status === 'done'" @click="doCancel">
                取消
              </n-button>
            </div>
          </div>

          <ol class="steps">
            <li v-for="s in current.steps" :key="s.idx" class="step" :class="`step--${s.status}`">
              <div class="step__head">
                <span class="step__idx">{{ s.idx + 1 }}</span>
                <code class="step__action">{{ s.action }}</code>
                <n-tag size="tiny" :type="STEP_TYPE[s.status]">{{ STEP_LABEL[s.status] }}</n-tag>
                <n-tag v-if="s.requires_human" size="tiny" type="error" :bordered="false">
                  需要人工确认
                </n-tag>
                <span v-if="s.duration_ms !== null" class="step__ms">{{ s.duration_ms }}ms</span>
              </div>
              <div v-if="s.description" class="step__desc">{{ s.description }}</div>

              <!-- 参数编辑：只有未执行的步骤可改 -->
              <div v-if="editing[s.idx] !== undefined" class="step__edit">
                <n-input
                  v-model:value="editing[s.idx]"
                  type="textarea"
                  :autosize="{ minRows: 3, maxRows: 8 }"
                  placeholder="参数 JSON"
                />
                <div class="step__edit-actions">
                  <n-button size="tiny" type="primary" @click="saveEdit(s.idx)">保存</n-button>
                  <n-button size="tiny" quaternary @click="cancelEdit(s.idx)">取消</n-button>
                </div>
              </div>
              <div v-else class="step__params">
                <code>{{ JSON.stringify(s.params) }}</code>
                <n-button
                  v-if="s.status === 'pending' || s.status === 'failed'"
                  size="tiny"
                  quaternary
                  @click="startEdit(s.idx, s.params)"
                >
                  改参数
                </n-button>
              </div>

              <pre v-if="s.error" class="step__error">{{ s.error }}</pre>
              <pre v-else-if="resultText(s.result)" class="step__result">{{ resultText(s.result) }}</pre>

              <n-button
                v-if="s.requires_human && !s.approved && s.status === 'pending'"
                size="tiny"
                type="warning"
                @click="doApprove(s.idx)"
              >
                确认执行
              </n-button>
            </li>
          </ol>

          <n-spin v-if="running" size="small" />
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.plans {
  padding: 24px 28px;
  height: 100%;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.plans__head h1 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 600;
}
.plans__hint {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
}
.plans__compose {
  display: flex;
  gap: 10px;
}
.plans__body {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 18px;
  min-height: 0;
  flex: 1;
}
.plans__list {
  border-right: 1px solid rgba(255, 255, 255, 0.07);
  padding-right: 12px;
  overflow: auto;
}
.plans__list-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 8px;
}
.plans__item {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 10px;
  margin-bottom: 6px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.03);
  color: inherit;
  cursor: pointer;
  text-align: left;
}
.plans__item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.plans__item--active {
  border-color: rgba(45, 212, 191, 0.4);
  background: rgba(45, 212, 191, 0.08);
}
.plans__item-goal {
  font-size: 13px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.plans__detail {
  overflow: auto;
  min-width: 0;
}
.plans__meta {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.plans__goal {
  font-size: 16px;
  font-weight: 600;
}
.plans__id {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 4px;
}
.plans__actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}
.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.step {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.02);
}
.step--done {
  border-color: rgba(24, 160, 88, 0.35);
}
.step--failed {
  border-color: rgba(208, 48, 80, 0.45);
}
.step--skipped {
  opacity: 0.75;
}
.step__head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step__idx {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  font-size: 12px;
  display: grid;
  place-items: center;
}
.step__action {
  font-size: 13px;
  color: #2dd4bf;
}
.step__ms {
  margin-left: auto;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
}
.step__desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  margin: 6px 0 0;
}
.step__params {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.step__params code {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
  background: rgba(255, 255, 255, 0.04);
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}
.step__edit {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.step__edit-actions {
  display: flex;
  gap: 8px;
}
.step__result,
.step__error {
  margin: 8px 0 0;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 160px;
  overflow: auto;
}
.step__result {
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.6);
}
.step__error {
  background: rgba(208, 48, 80, 0.12);
  color: #ff8ba0;
}
</style>
