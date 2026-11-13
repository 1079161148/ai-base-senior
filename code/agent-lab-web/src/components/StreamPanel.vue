<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import { streamDemo, type StreamChunk } from '../api/stream'

const draft = ref('你好，我是流式输出的演示内容。注意看文字是一个一个出现的。')
const output = ref('')
const running = ref(false)
const error = ref('')
const usage = ref<StreamChunk['usage'] | null>(null)

let controller: AbortController | null = null

const canStart = computed(() => !running.value && draft.value.trim().length > 0)

async function start() {
  if (!canStart.value) return

  output.value = ''
  usage.value = null
  error.value = ''
  running.value = true
  controller = new AbortController()

  try {
    await streamDemo({
      text: draft.value.trim(),
      signal: controller.signal,
      onChunk: (chunk) => {
        if (chunk.delta) output.value += chunk.delta
        if (chunk.done) usage.value = chunk.usage ?? null
      },
    })
  } catch (e) {
    // 用户主动点「停止」会抛 AbortError —— 那是预期行为，不是错误
    const isAbort = e instanceof DOMException && e.name === 'AbortError'
    if (!isAbort) {
      error.value = e instanceof Error ? e.message : '流式请求失败'
    }
  } finally {
    running.value = false
    controller = null
  }
}

/**
 * 中断当前流。
 *
 * abort() 不传参时，Chrome 会在控制台打：
 *   AbortError: signal is aborted without reason
 * 看起来像 bug，其实是浏览器的网络层在给被拆除的响应收尾。
 *
 * 传一个 DOMException 作为 reason，日志就变成：
 *   AbortError: 用户主动停止
 * 同样的机制，但一眼能看懂是谁触发的。
 *
 * 注意：reason 的 name 必须仍是 'AbortError'，否则 start() 里的
 * `e.name === 'AbortError'` 判断会失效，用户会把正常停止看成失败。
 */
function stop(reason = '用户主动停止') {
  controller?.abort(new DOMException(reason, 'AbortError'))
}

// 组件卸载时一定要中断，否则离开页面后连接还挂着
onBeforeUnmount(() => stop('组件已卸载'))
</script>

<template>
  <section class="panel">
    <div class="panel__head">
      <h2>
        流式输出
        <span class="panel__badge">SSE</span>
      </h2>
      <span v-if="usage" class="panel__usage">
        {{ usage.chars }} 字 · ¥{{ usage.cost_cny }}
      </span>
    </div>

    <form class="row" @submit.prevent="start">
      <input v-model="draft" class="input" type="text" placeholder="要推送的文本" maxlength="200" />
      <button v-if="!running" class="btn btn--primary" type="submit" :disabled="!canStart">
        开始
      </button>
      <!-- 必须写 stop() 而不是 stop：后者会把 MouseEvent 当第一个参数传给 stop() -->
      <button v-else class="btn btn--danger" type="button" @click="stop()">停止</button>
    </form>

    <p v-if="error" class="alert">{{ error }}</p>

    <div class="stream" :class="{ 'stream--live': running }">
      <p v-if="!output && !running" class="state">点「开始」逐字接收。</p>
      <p v-else class="stream__text">{{ output }}<span v-if="running" class="caret" /></p>
    </div>
  </section>
</template>
