<script setup lang="ts">
/**
 * S9 · 登录 / 注册。
 *
 * 一个页面做两件事：默认是登录，点"注册"切过去。
 * 不拆两个路由 —— 登录场景不需要那么重的结构。
 */
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NInput, NButton, NForm, NFormItem, NAlert, useMessage } from 'naive-ui'
import { login, register, saveAuth } from '../api/auth'
import { ApiError } from '../api/http'

const router = useRouter()
const route = useRoute()
const message = useMessage()

const mode = ref<'login' | 'register'>('login')
const username = ref('demo')
const password = ref('demo123')
const displayName = ref('')
const loading = ref(false)
const error = ref('')

const isRegister = computed(() => mode.value === 'register')
const canSubmit = computed(
  () => username.value.trim().length > 0 && password.value.length > 0,
)

function switchMode() {
  mode.value = isRegister.value ? 'login' : 'register'
  error.value = ''
}

async function submit() {
  if (!canSubmit.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const result = isRegister.value
      ? await register(username.value.trim(), password.value, displayName.value.trim())
      : await login(username.value.trim(), password.value)

    saveAuth(result)

    // 登录前想去的页面（被守卫拦下来的那个）
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
    message.success(`欢迎，${result.user.display_name || result.user.username}`)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '登录失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="login__card">
      <div class="login__brand">
        <div class="login__mark">A</div>
        <div>
          <div class="login__name">agent-lab</div>
          <div class="login__sub">一个五脏俱全的 Agent 项目</div>
        </div>
      </div>

      <h1 class="login__title">{{ isRegister ? '注册新账号' : '登录' }}</h1>

      <n-form @keydown.enter.prevent="submit">
        <n-form-item label="用户名">
          <n-input v-model:value="username" placeholder="用户名" :disabled="loading" />
        </n-form-item>

        <n-form-item label="密码">
          <n-input
            v-model:value="password"
            type="password"
            show-password-on="click"
            placeholder="密码"
            :disabled="loading"
          />
        </n-form-item>

        <n-form-item v-if="isRegister" label="显示名（可选）">
          <n-input v-model:value="displayName" placeholder="别人看到的名字" :disabled="loading" />
        </n-form-item>

        <n-alert v-if="error" type="error" :bordered="false" class="login__error">
          {{ error }}
        </n-alert>

        <n-button
          type="primary"
          block
          :loading="loading"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{ isRegister ? '注册并登录' : '登录' }}
        </n-button>
      </n-form>

      <div class="login__switch">
        <n-button text type="info" @click="switchMode">
          {{ isRegister ? '已有账号？去登录' : '没有账号？注册一个' }}
        </n-button>
      </div>

      <p class="login__hint">
        演示账号 <code>demo / demo123</code>，已预置待办、文档和会话数据。
      </p>
    </div>
  </div>
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  box-sizing: border-box;
}

.login__card {
  width: min(380px, 100%);
  padding: 28px 26px 22px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
}

.login__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 22px;
}
.login__mark {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-weight: 700;
  color: #2dd4bf;
  background: rgba(45, 212, 191, 0.14);
  border: 1px solid rgba(45, 212, 191, 0.22);
}
.login__name {
  font-size: 14px;
  font-weight: 700;
  color: #e6edf3;
}
.login__sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}

.login__title {
  margin: 0 0 18px;
  font-size: 18px;
  font-weight: 600;
  color: #e6edf3;
}

.login__error {
  margin-bottom: 12px;
}

.login__switch {
  margin-top: 14px;
  text-align: center;
}

.login__hint {
  margin: 18px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.35);
  text-align: center;
}
.login__hint code {
  color: #2dd4bf;
}
</style>
