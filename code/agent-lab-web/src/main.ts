import { createApp } from 'vue'
import { createPinia } from 'pinia'
import naive from 'naive-ui'
import router from './router'
import App from './App.vue'
import { installAuthFetch } from './api/auth'
import './style.css'

// 必须在任何组件发请求之前装好：
// 它负责给所有 /api/ 请求带上 token，并在 401 时统一跳登录。
installAuthFetch()

const app = createApp(App)
app.use(createPinia())
app.use(router)
// 全局注册 Naive UI 的全部组件。
// 不注册的话模板里的 <n-config-provider> / <n-message-provider> / <n-menu>
// 会被 Vue 当成未知自定义元素跳过渲染，useMessage() 也随之找不到 Provider。
app.use(naive)
app.mount('#app')
