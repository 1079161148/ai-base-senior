/**
 * 时间展示的唯一入口。
 *
 * 分工约定：
 *   后端 —— 只负责"准确的时刻"，一律返回带时区的 ISO 8601（默认 UTC，形如
 *           `2026-11-08T15:01:27+00:00`）。
 *   前端 —— 只负责"好读的呈现"，在这里统一转成用户浏览器所在时区。
 *
 * **任何组件要显示时间都调本文件，不要自己写 `new Date().toLocaleString()`。**
 * 否则同一个页面很快会出现三种格式：有的带秒、有的不带、有的还是 UTC。
 */

/** 后端可能返回的三种格式都要覆盖 */
export function parseTime(input: string): Date | null {
  // ① 后端 TIME_FORMAT=human 时返回「2026-11-08 23:10:58」
  //    Safari 会把它判成 Invalid Date，所以手动拆字段构造
  const human = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/.exec(input)
  if (human) {
    const [, y, mo, d, h, mi, s] = human
    return new Date(+y!, +mo! - 1, +d!, +h!, +mi!, +s!)
  }

  // ② 标准 ISO（带时区）或 ③ 无时区的旧数据，交给 Date 原生解析
  const d = new Date(input)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * 完整时间：`11-08 23:01`
 * 用于列表行内展示 —— 空间有限，去掉年份。
 */
export function formatDateTime(input: string): string {
  const d = parseTime(input)
  // 解析失败就原样返回，绝不显示 "Invalid Date"
  if (!d) return input

  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/**
 * 完整到秒：`2026-11-08 23:01:27`
 * 用于详情页、日志这类需要精确核对的地方。
 */
export function formatDateTimeFull(input: string): string {
  const d = parseTime(input)
  if (!d) return input

  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}
