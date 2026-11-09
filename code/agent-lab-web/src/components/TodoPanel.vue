<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiError } from '../api/http'
import { todoApi, type Todo } from '../api/todos'
import { formatDateTime } from '../utils/time'

const todos = ref<Todo[]>([])
const draft = ref('')
const loading = ref(false)
/** 正在操作的那一条，用于禁用单个条目而不是整个列表 */
const pending = ref<number | null>(null)
const error = ref('')

function toMessage(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback
}

// 时间格式化统一放在 utils/time.ts，本组件不再自己 new Date()。
// 这样以后任何组件要显示时间，格式都不会跑偏。

async function load() {
  loading.value = true
  error.value = ''
  try {
    todos.value = await todoApi.list()
  } catch (e) {
    error.value = toMessage(e, '加载失败')
  } finally {
    loading.value = false
  }
}

async function add() {
  const title = draft.value.trim()
  if (!title || loading.value) return

  loading.value = true
  error.value = ''
  try {
    const created = await todoApi.create({ title })
    // 后端按 id DESC 排序，新记录一定在最前
    todos.value = [created, ...todos.value]
    draft.value = ''
  } catch (e) {
    error.value = toMessage(e, '创建失败')
  } finally {
    loading.value = false
  }
}

/** 404 表示「目标已不存在」——对更新/删除来说属于数据过期，而不是操作失败 */
function isNotFound(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404
}

function dropLocal(id: number): void {
  todos.value = todos.value.filter((t) => t.id !== id)
}

async function toggle(todo: Todo) {
  pending.value = todo.id
  error.value = ''
  try {
    // 用后端返回的对象替换本地副本，避免前后端状态漂移
    const updated = await todoApi.update(todo.id, { done: !todo.done })
    todos.value = todos.value.map((t) => (t.id === updated.id ? updated : t))
  } catch (e) {
    if (isNotFound(e)) {
      // 后端已经没有这一条了（别处删过、或本地列表过期）。
      // 这不是操作失败，而是数据不一致：本地同步移除即可，不要弹错误打扰用户。
      dropLocal(todo.id)
    } else {
      error.value = toMessage(e, '更新失败')
      // 真失败（网络/500）时重新拉一次，把乐观更新造成的假象纠正回来
      await load()
    }
  } finally {
    pending.value = null
  }
}

async function remove(todo: Todo) {
  pending.value = todo.id
  error.value = ''
  try {
    await todoApi.remove(todo.id)
    dropLocal(todo.id)
  } catch (e) {
    if (isNotFound(e)) {
      // 删除的目标本来就不存在 —— 目标已达成（幂等），静默移除
      dropLocal(todo.id)
    } else {
      error.value = toMessage(e, '删除失败')
    }
  } finally {
    pending.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="panel">
    <div class="panel__head">
      <h2>
        待办
        <span class="panel__count">{{ todos.length }}</span>
      </h2>
      <button class="btn btn--ghost" :disabled="loading" @click="load">刷新</button>
    </div>

    <form class="row" @submit.prevent="add">
      <input
        v-model="draft"
        class="input"
        type="text"
        placeholder="写点什么，回车添加…"
        maxlength="200"
      />
      <button class="btn btn--primary" type="submit" :disabled="!draft.trim() || loading">
        添加
      </button>
    </form>

    <p v-if="error" class="alert">{{ error }}</p>

    <ul v-if="todos.length" class="todo-list">
      <li
        v-for="t in todos"
        :key="t.id"
        class="todo"
        :class="{ 'todo--done': t.done, 'todo--busy': pending === t.id }"
      >
        <label class="todo__check">
          <input
            type="checkbox"
            :checked="t.done"
            :disabled="pending === t.id"
            @change="toggle(t)"
          />
          <span class="todo__title">{{ t.title }}</span>
          <!-- <time> 是语义化标签，datetime 保留原始值，方便爬虫/读屏软件读取 -->
          <time class="todo__time" :datetime="t.created_at">{{ formatDateTime(t.created_at) }}</time>
        </label>
        <button
          class="todo__del"
          type="button"
          title="删除"
          :disabled="pending === t.id"
          @click="remove(t)"
        >
          ✕
        </button>
      </li>
    </ul>

    <p v-else-if="loading" class="state">加载中…</p>
    <p v-else class="state">还没有待办，添加第一条试试。</p>
  </section>
</template>
