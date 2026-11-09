/**
 * `.vue` 单文件组件的类型声明。
 *
 * 为什么需要它：
 *   `.vue` 不是标准 TypeScript 能识别的文件，必须靠语言服务插件（Volar / vue-tsc）
 *   才能解析。如果编辑器里没有启用 Vue 语言支持，或者 TS 服务版本较旧，
 *   所有 `import Xxx from './Xxx.vue'` 都会报：
 *       error TS2307: Cannot find module './Xxx.vue' or its corresponding type declarations.
 *   一报就是十几条，看起来像"到处是错"，其实都是同一个原因。
 *
 * 有了这个声明，标准 tsc 也会把 `.vue` 当成一个组件模块。
 * 注意：Volar / vue-tsc 会**优先**解析真实的 .vue 文件，拿到精确的 props 类型，
 * 所以这段声明不会让类型变弱，只是兜底。
 */

declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent
  export default component
}
