<script setup lang="ts">
import StreamPanel from './components/StreamPanel.vue'
import TodoPanel from './components/TodoPanel.vue'
</script>

<template>
  <div class="shell">
    <header class="shell__header">
      <div class="brand">
        <span class="brand__mark">◆</span>
        <div>
          <h1 class="brand__title">agent-lab</h1>
          <p class="brand__sub">S0 · FastAPI + Vue3 联调台</p>
        </div>
      </div>

      <a class="link" href="http://127.0.0.1:8001/docs" target="_blank" rel="noreferrer">
        后端 /docs ↗
      </a>
    </header>

    <main class="shell__main">
      <TodoPanel />
      <StreamPanel />
    </main>

    <footer class="shell__footer">
      请求经 Vite 代理 <code>/api</code> → <code>127.0.0.1:8001</code>
    </footer>
  </div>
</template>
