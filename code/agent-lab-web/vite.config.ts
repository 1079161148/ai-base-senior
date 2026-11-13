import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // 固定 IPv4。Vite 默认 host 是 'localhost'，在 Windows 上可能只绑定 [::1]，
    // 导致 http://127.0.0.1:9999 连不上（浏览器用 localhost 访问则正常，但代理/脚本会挂）
    host: '127.0.0.1',
    port: 9999,
    // 端口被占用时直接报错，而不是悄悄切到 9998 —— 否则代理脚本会连错端口
    strictPort: true,
    proxy: {
      // 开发期把 /api 转发给 FastAPI。
      // 好处：业务代码里只写 /api/v1/xxx，
      //   - 不把 http://127.0.0.1:8001 硬编码进组件
      //   - 同源请求，不必依赖 CORS（后端配了，但代理后更省心）
      // 生产环境由 Nginx / 网关做同样的转发。
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        // SSE 必须关闭缓冲，否则 Vite 代理可能攒一批再下发
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache'
            }
          })
        },
      },
    },
  },
})
