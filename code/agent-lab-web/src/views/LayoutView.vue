<script setup lang="ts">
import { h, ref, computed, onMounted, onBeforeUnmount, type Component } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NIcon, NMenu, NLayout, NLayoutSider, NButton, NPopconfirm,
} from 'naive-ui'
import {
  ChatbubblesOutline as ChatIcon,
  DocumentTextOutline as DocIcon,
  ListOutline as PlanIcon,
  StatsChartOutline as MetricsIcon,
  TimeOutline as SessionIcon,
  PulseOutline as TraceIcon,
  LogOutOutline as LogoutIcon,
  PersonCircleOutline as UserIcon,
} from '@vicons/ionicons5'
import { clearAuth, getStoredUser } from '../api/auth'

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)

const user = getStoredUser()

/**
 * 移动端断点。
 *
 * 用 matchMedia 而不是纯 CSS：侧栏在窄屏要"脱离文档流"（fixed 抽屉），
 * 而这会让 NLayout 的 flex 排布失效 —— 必须让 JS 知道当前模式，
 * 才能同时控制遮罩层和折叠状态。
 */
const MOBILE_QUERY = '(max-width: 768px)'
// matchMedia 对象必须建在 setup 顶层：
// 生命周期钩子只能在 setup 同步执行期间注册，
// 写在 onMounted 回调里等于没注册，卸载时也就永远摘不掉监听。
const mql = window.matchMedia(MOBILE_QUERY)
const isMobile = ref(mql.matches)
const menuOpen = ref(false)

function onViewportChange(e: MediaQueryListEvent) {
  isMobile.value = e.matches
  // 从窄屏切回宽屏时，抽屉状态必须清掉，否则遮罩会留在屏幕上
  if (!e.matches) menuOpen.value = false
}

onMounted(() => mql.addEventListener('change', onViewportChange))
onBeforeUnmount(() => mql.removeEventListener('change', onViewportChange))

/**
 * 退出登录。
 *
 * 只清本地 token，不调后端 —— JWT 是无状态的，服务端没有会话可注销。
 * 想做到"立即踢下线"需要维护黑名单或改用短 token + refresh token，
 * 那是另一个量级的设计，这里不需要。
 */
function logout() {
  clearAuth()
  router.replace('/login')
}

function renderIcon(icon: Component) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

interface NavItem { label: string; key: string; icon: Component }

const navItems: NavItem[] = [
  { label: '对话', key: '/', icon: ChatIcon },
  { label: '文档', key: '/documents', icon: DocIcon },
  { label: '会话', key: '/sessions', icon: SessionIcon },
  { label: '计划', key: '/plans', icon: PlanIcon },
  { label: '指标', key: '/metrics', icon: MetricsIcon },
  { label: 'Trace', key: '/traces', icon: TraceIcon },
]

const menuOptions = computed(() =>
  navItems.map(i => ({ label: i.label, key: i.key, icon: renderIcon(i.icon) })),
)

/** 当前高亮项。子路由（如 /documents）直接命中，其余归到 '/' */
const activeKey = computed(() => (route.path === '/' ? '/' : route.path))

function onSelect(key: string) {
  if (key !== route.path) router.push(key)
  // 移动端选完菜单要自动收起，否则抽屉挡着内容
  if (isMobile.value) menuOpen.value = false
}
</script>

<template>
  <!-- has-sider 是关键：没有它 NLayout 不会切成 flex 横向布局，
       侧栏会变成块级元素，宽度/高度都会塌掉。 -->
  <n-layout
    has-sider
    position="absolute"
    class="app-shell"
    :class="{ 'app-shell--mobile': isMobile, 'app-shell--menu': menuOpen }"
  >
    <n-layout-sider
      bordered
      collapse-mode="width"
      :width="216"
      :collapsed-width="64"
      :collapsed="collapsed"
      :native-scrollbar="false"
      :show-trigger="!isMobile"
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <!-- 品牌区 -->
      <div class="brand" :class="{ 'brand--mini': collapsed }">
        <div class="brand__mark">A</div>
        <div v-if="!collapsed" class="brand__text">
          <div class="brand__name">agent-lab</div>
          <div class="brand__sub">S9 · 鉴权与多租户</div>
        </div>
      </div>

      <n-menu
        :value="activeKey"
        :options="menuOptions"
        :collapsed="collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="20"
        :indent="18"
        class="app-menu"
        @update:value="onSelect"
      />

      <!-- 用户区：固定在侧栏底部 -->
      <div class="user" :class="{ 'user--mini': collapsed }">
        <n-icon size="18" class="user__icon"><UserIcon /></n-icon>
        <div v-if="!collapsed" class="user__info">
          <div class="user__name">{{ user?.display_name || user?.username || '未登录' }}</div>
          <div class="user__id">{{ user?.username }}</div>
        </div>
        <n-popconfirm v-if="!collapsed" @positive-click="logout">
          <template #trigger>
            <n-button text size="tiny" class="user__logout">
              <n-icon><LogoutIcon /></n-icon>
            </n-button>
          </template>
          退出登录？
        </n-popconfirm>
      </div>
    </n-layout-sider>

    <!-- 移动端：侧栏变成抽屉，这是唯一的入口 -->
    <button v-if="isMobile" class="mobile-fab" @click="menuOpen = true">
      <span class="mobile-fab__bar" />
      <span class="mobile-fab__bar" />
      <span class="mobile-fab__bar" />
    </button>
    <div v-if="isMobile && menuOpen" class="mobile-mask" @click="menuOpen = false" />

    <main class="app-main">
      <router-view />
    </main>
  </n-layout>
</template>

<style scoped>
.app-shell {
  height: 100vh;
}

/* sider 内部要能撑满：品牌区在顶、菜单在中间、用户区贴底 */
:deep(.n-layout-sider-scroll-container) {
  display: flex;
  flex-direction: column;
}

/* ---- 用户区 ---- */
.user {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.user--mini {
  justify-content: center;
  padding: 12px 0;
}
.user__icon {
  color: rgba(255, 255, 255, 0.45);
  flex: none;
}
.user__info {
  flex: 1;
  min-width: 0;
}
.user__name {
  font-size: 12px;
  color: #e6edf3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user__id {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.32);
}
.user__logout {
  color: rgba(255, 255, 255, 0.4);
}

/* ---- 品牌区 ---- */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 18px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.brand--mini {
  justify-content: center;
  padding: 18px 0 16px;
}
.brand__mark {
  flex: none;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 15px;
  color: #2dd4bf;
  background: rgba(45, 212, 191, 0.14);
  border: 1px solid rgba(45, 212, 191, 0.22);
}
.brand__name {
  font-size: 14px;
  font-weight: 700;
  color: #e6edf3;
  letter-spacing: 0.2px;
  line-height: 1.25;
}
.brand__sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.32);
  line-height: 1.3;
}

/* ---- 菜单 ---- */
.app-menu {
  padding: 8px 6px;
}

/* ---- 主区域 ---- */
.app-main {
  flex: 1;
  min-width: 0;
  height: 100vh;
  padding: 24px;
  box-sizing: border-box;
  overflow-y: auto;
}

/* ---- 移动端 ---- */
/* 侧栏脱离文档流变成抽屉：宽度不再挤压内容，transform 做位移动画 */
.app-shell--mobile :deep(.n-layout-sider) {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1002;
  height: 100vh;
  transform: translateX(-100%);
  transition: transform 0.2s ease;
}
.app-shell--mobile.app-shell--menu :deep(.n-layout-sider) {
  transform: none;
}
.app-shell--mobile .app-main {
  padding: 56px 14px 14px;
}

.mobile-mask {
  position: fixed;
  inset: 0;
  z-index: 1001;
  background: rgba(0, 0, 0, 0.45);
}

.mobile-fab {
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 1000;
  width: 36px;
  height: 36px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  padding: 0 9px;
  border-radius: 9px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.mobile-fab__bar {
  display: block;
  height: 2px;
  border-radius: 1px;
  background: rgba(255, 255, 255, 0.65);
}
</style>