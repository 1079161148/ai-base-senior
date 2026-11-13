import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

/** 流式 Markdown 渲染器：处理未闭合代码块、不完整表格 */
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch { /* fall through */ }
    }
    return md.utils.escapeHtml(code)
  },
})

// 外链必须新开窗口。
// 不设 target 的话，点击回答里的链接会把整个 SPA 导航走，
// 聊天记录和流式连接全丢 —— 用户按返回键回来还要等重新加载。
//
// noopener 不是可选项：不设的话新页面能通过 window.opener 把原页面改掉（tabnabbing）。
const defaultLinkOpen =
  md.renderer.rules.link_open ??
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  if (token) {
    token.attrSet('target', '_blank')
    token.attrSet('rel', 'noopener noreferrer')
  }
  return defaultLinkOpen(tokens, idx, options, env, self)
}

/**
 * 渲染 Markdown 为 HTML。
 * 流式场景下代码块可能未闭合，这里做容错处理。
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  // 补齐未闭合的代码块
  let fixed = text
  const ticks = (fixed.match(/```/g) || []).length
  if (ticks % 2 !== 0) fixed += '\n```'
  try {
    return md.render(fixed)
  } catch {
    return md.utils.escapeHtml(text)
  }
}

/**
 * 提取纯文本（用于标题生成等场景）
 *
 * 表格要单独处理：Markdown 表格的 `| a | b |` 和 `|---|---|` 行
 * 在单行标题里没法渲染成表格，留着就是一堆竖线和横杠，必须整行丢弃。
 */
export function stripMarkdown(text: string): string {
  const withoutTables = text
    .split('\n')
    .filter((line) => {
      const t = line.trim()
      if (!t) return false
      // 表格数据行：以 | 开头
      if (t.startsWith('|')) return false
      // 表格分隔行：|---|---| 或 --- | ---
      if (/^[|\s:-]*-[|\s:-]*$/.test(t) && t.includes('|')) return false
      return true
    })
    .join('\n')

  return withoutTables
    .replace(/```[\s\S]*?```/g, '[代码]')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/#{1,6}\s/g, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/[*_]/g, '')
    .trim()
}