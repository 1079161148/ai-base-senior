import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn } from '../api/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      // 登录页必须在 Layout 之外：它不该有侧边栏
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      component: () => import('../views/LayoutView.vue'),
      children: [
        {
          path: '',
          name: 'chat',
          component: () => import('../views/ChatView.vue'),
          meta: { title: '对话' },
        },
        {
          path: 'documents',
          name: 'documents',
          component: () => import('../views/DocumentsView.vue'),
          meta: { title: '文档管理' },
        },
        {
          path: 'sessions',
          name: 'sessions',
          component: () => import('../views/SessionsView.vue'),
          meta: { title: '会话管理' },
        },
        {
          path: 'plans',
          name: 'plans',
          component: () => import('../views/PlansView.vue'),
          meta: { title: '任务计划' },
        },
        {
          path: 'metrics',
          name: 'metrics',
          component: () => import('../views/MetricsView.vue'),
          meta: { title: '运行指标' },
        },
        {
          path: 'traces',
          name: 'traces',
          component: () => import('../views/TracesView.vue'),
          meta: { title: 'Trace 回放' },
        },
      ],
    },
  ],
})

/**
 * 路由守卫。
 *
 * 注意这只是**体验层**的门：真正的权限在后端每个接口的 CurrentUserDep 上。
 * 前端守卫能被绕过（改 localStorage 就行），所以绝不能把它当安全边界 ——
 * 它的作用是"未登录时不要先加载一堆页面再看到满屏 401"。
 */
router.beforeEach((to) => {
  const logged = isLoggedIn()

  if (!to.meta.public && !logged) {
    // 记住原本要去哪，登录后直接送过去
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.path === '/login' && logged) {
    return { path: '/' }
  }

  return true
})

export default router
