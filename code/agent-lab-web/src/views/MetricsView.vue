<script setup lang="ts">
/**
 * S7 · 看板。
 *
 * 判断标准只有一条：**一屏能不能决定"今天能不能发版"**。
 * 所以四个数字放最上面，失败样例放最下面，中间的明细可以慢慢看。
 */
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NEmpty,
  NSpin,
  NTag,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'
import {
  fetchFailures,
  fetchSummary,
  type FailureRow,
  type MetricsSummary,
} from '../api/metrics'
import { ApiError } from '../api/http'

const message = useMessage()

const days = ref(7)
const loading = ref(false)
const data = ref<MetricsSummary | null>(null)
const failures = ref<FailureRow[]>([])

const isEmpty = computed(() => (data.value?.requests ?? 0) === 0)

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`
}

function money(v: number) {
  return `¥${v.toFixed(4)}`
}

const failureColumns: DataTableColumns<FailureRow> = [
  {
    title: '时间',
    key: 'started_at',
    width: 150,
    render: (r) => r.started_at.slice(0, 16).replace('T', ' '),
  },
  { title: '问题', key: 'question', ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render: (r) =>
      h(NTag, { size: 'tiny', type: 'error', bordered: false }, { default: () => r.status }),
  },
  {
    title: '耗时',
    key: 'duration_ms',
    width: 90,
    render: (r) => `${Math.round(r.duration_ms)}ms`,
  },
  { title: 'trace', key: 'trace_id', width: 180 },
]

async function load() {
  loading.value = true
  try {
    data.value = await fetchSummary(days.value)
    failures.value = await fetchFailures(10)
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : '加载指标失败')
  } finally {
    loading.value = false
  }
}

function switchDays(d: number) {
  days.value = d
  load()
}

/** 按天柱状图的高度（百分比）。没有数据时给 2%，避免柱体消失 */
function barHeight(p95: number): string {
  const max = Math.max(...(data.value?.by_day.map((d) => d.p95_ms) ?? [1]), 1)
  return `${Math.max(2, Math.round((p95 / max) * 100))}%`
}

onMounted(load)
</script>

<template>
  <div class="metrics">
    <header class="metrics__head">
      <div>
        <h1>运行指标</h1>
        <p class="metrics__hint">成功率 / 延迟 / 成本 一起看 —— 只看一个数会做错决定。</p>
      </div>
      <div class="metrics__range">
        <n-button
          v-for="d in [1, 7, 30]"
          :key="d"
          size="tiny"
          :type="days === d ? 'primary' : 'default'"
          @click="switchDays(d)"
        >
          {{ d }} 天
        </n-button>
        <n-button size="tiny" quaternary :loading="loading" @click="load">刷新</n-button>
      </div>
    </header>

    <n-spin :show="loading">
      <n-empty v-if="isEmpty" description="窗口内还没有请求，先去聊两句" />

      <template v-else-if="data">
        <div class="cards">
          <div class="card">
            <div class="card__label">成功率</div>
            <div class="card__value" :class="{ 'card__value--bad': data.success_rate < 0.9 }">
              {{ pct(data.success_rate) }}
            </div>
            <div class="card__sub">{{ data.requests }} 次请求</div>
          </div>
          <div class="card">
            <div class="card__label">P95 延迟</div>
            <div class="card__value" :class="{ 'card__value--bad': data.p95_ms > 8000 }">
              {{ (data.p95_ms / 1000).toFixed(1) }}s
            </div>
            <div class="card__sub">P50 {{ Math.round(data.p50_ms) }}ms</div>
          </div>
          <div class="card">
            <div class="card__label">单任务成本</div>
            <div class="card__value">{{ money(data.avg_cost_cny) }}</div>
            <div class="card__sub">合计 {{ money(data.total_cost_cny) }}</div>
          </div>
          <div class="card">
            <div class="card__label">工具调用</div>
            <div class="card__value">{{ data.total_tool_calls }}</div>
            <div class="card__sub">{{ Object.entries(data.by_status).map(([k, v]) => `${k}:${v}`).join(' · ') }}</div>
          </div>
        </div>

        <section class="panel">
          <div class="panel__title">每日 P95 延迟</div>
          <div class="bars">
            <div v-for="d in data.by_day" :key="d.date" class="bar">
              <div class="bar__fill" :style="{ height: barHeight(d.p95_ms) }" />
              <div class="bar__value">{{ Math.round(d.p95_ms) }}</div>
              <div class="bar__label">{{ d.date.slice(5) }}</div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel__title">按配置指纹分组</div>
          <p class="panel__hint">
            指纹 = 模型 + 温度 + max_tokens + 提示词版本 + 工具版本的哈希。改一次提示词就会换一组，用来归因"是哪次改动让指标变了"。
          </p>
          <table class="fp">
            <thead>
              <tr>
                <th>指纹</th>
                <th>模型</th>
                <th>请求</th>
                <th>成功率</th>
                <th>单次成本</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in data.by_fingerprint" :key="f.fingerprint">
                <td><code>{{ f.fingerprint }}</code></td>
                <td>{{ f.model }}</td>
                <td>{{ f.requests }}</td>
                <td>{{ pct(f.success_rate) }}</td>
                <td>{{ money(f.avg_cost_cny) }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="panel">
          <div class="panel__title">最近失败（{{ failures.length }}）</div>
          <n-empty v-if="failures.length === 0" size="small" description="没有失败记录" />
          <n-data-table
            v-else
            :columns="failureColumns"
            :data="failures"
            :bordered="false"
            size="small"
          />
        </section>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.metrics {
  padding: 24px 28px;
  height: 100%;
  overflow: auto;
}
.metrics__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}
.metrics__head h1 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 600;
}
.metrics__hint {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
}
.metrics__range {
  display: flex;
  gap: 6px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.card {
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 10px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.02);
}
.card__label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
.card__value {
  font-size: 26px;
  font-weight: 600;
  margin: 6px 0 2px;
  color: #2dd4bf;
}
.card__value--bad {
  color: #ff8ba0;
}
.card__sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.panel {
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.panel__title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
}
.panel__hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1.5;
}
.bars {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  height: 140px;
}
.bar {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
  height: 100%;
  gap: 4px;
}
.bar__fill {
  width: 100%;
  max-width: 42px;
  background: linear-gradient(180deg, rgba(45, 212, 191, 0.9), rgba(45, 212, 191, 0.25));
  border-radius: 4px 4px 0 0;
}
.bar__value {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}
.bar__label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}
.fp {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.fp th,
.fp td {
  text-align: left;
  padding: 6px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.fp th {
  color: rgba(255, 255, 255, 0.45);
  font-weight: 500;
}
.fp code {
  color: #2dd4bf;
}
</style>
