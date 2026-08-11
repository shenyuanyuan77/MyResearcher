<template>
  <svg
    :width="size"
    :height="size"
    :viewBox="`0 0 24 24`"
    :fill="filled ? 'currentColor' : 'none'"
    :stroke="filled ? 'none' : 'currentColor'"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    :aria-hidden="decorative ? 'true' : undefined"
    :aria-label="ariaLabel"
    :role="ariaLabel ? 'img' : undefined"
    class="app-icon"
    :style="{ color }"
  >
    <g v-html="path"></g>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
  strokeWidth: { type: [Number, String], default: 1.75 },
  filled: { type: Boolean, default: false },
  color: { type: String, default: 'currentColor' },
  ariaLabel: { type: String, default: '' },
  decorative: { type: Boolean, default: false },
})

/* SF Symbol 风格 24×24 线性图标 path。filled = true 时用 fill=currentColor。 */
const ICONS = {
  // 用户 / 助手
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-3.31 0-7 1.79-7 5v1h14v-1c0-3.21-3.69-5-7-5Z',
  bot: 'M5 8h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-9l-5 3v-3H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Z M9 12h.01 M15 12h.01',
  sparkles: 'M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3Z M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14Z M5 14l.6 1.4L7 16l-1.4.6L5 18l-.6-1.4L3 16l1.4-.6L5 14Z',

  // 工具 / 状态
  wrench: 'M14.7 6.3a4 4 0 1 0 5 5l-2.4-2.4 2.4-2.4-2.6-.2-2.4 0Z M3 21l8-8',
  tool: 'M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.4 2.4-2.6 0-2.4-2.4 2.4-2.4 2.6 0 2.4 2.4Z',
  hammer: 'M13 3l8 8-3 3-2-2-7 7-3-3 7-7-2-2 2-4Z',
  chartBar: 'M4 20V10 M10 20V4 M16 20v-7 M22 20H2',
  chartLine: 'M3 17l6-6 4 4 8-9 M14 6h7v7',
  pie: 'M12 2a10 10 0 1 0 10 10h-10V2Z M12 2a10 10 0 0 1 10 10h-10V2Z',
  search: 'M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14Z M21 21l-4.3-4.3',
  book: 'M4 5a2 2 0 0 1 2-2h13v18H6a2 2 0 0 1-2-2V5Z M19 16H6a2 2 0 0 0-2 2',
  layers: 'M12 2L3 7l9 5 9-5-9-5Z M3 12l9 5 9-5 M3 17l9 5 9-5',
  cube: 'M12 2 3 7v10l9 5 9-5V7l-9-5Z M12 2v10 M3 7l9 5 9-5',
  doc: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z M14 3v5h5 M9 13h6 M9 17h6 M9 9h2',
  clipboard: 'M9 4h6a2 2 0 0 1 2 2v14H7V6a2 2 0 0 1 2-2Z M9 4V3a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1',
  pencil: 'M14 4l6 6L8 22H2v-6L14 4Z M13 5l6 6',

  // 通信 / 输入
  paperPlane: 'M22 2L11 13 M22 2l-7 20-4-9-9-4 20-7Z',
  envelope: 'M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z M22 7l-10 6L2 7',
  link: 'M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66L11 7 M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66L13 17',
  attachment: 'M21.4 11l-9.2 9.2a5 5 0 0 1-7-7l9.2-9.2a3.5 3.5 0 0 1 5 5L10.2 18a2 2 0 0 1-3-3l8.5-8.5',

  // 行为 / 反馈
  check: 'M5 12l5 5 9-11',
  cross: 'M18 6L6 18 M6 6l12 12',
  plus: 'M12 5v14 M5 12h14',
  minus: 'M5 12h14',
  chevronRight: 'M9 6l6 6-6 6',
  chevronLeft: 'M15 6l-6 6 6 6',
  chevronDown: 'M6 9l6 6 6-6',
  chevronUp: 'M6 15l6-6 6 6',
  arrowUp: 'M12 19V5 M5 12l7-7 7 7',
  arrowDown: 'M12 5v14 M5 12l7 7 7-7',
  arrowUpRight: 'M7 17 17 7 M7 7h10v10',
  arrowDownRight: 'M7 7 17 17 M17 7v10h-10',
  refresh: 'M3 12a9 9 0 0 1 15-6.7L21 8 M21 3v5h-5 M21 12a9 9 0 0 1-15 6.7L3 16 M3 21v-5h5',
  trash: 'M4 7h16 M10 11v6 M14 11v6 M5 7l1 13a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-13 M9 7V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v3',
  filter: 'M4 4h16l-6 8v6l-4 2v-8L4 4Z',
  sort: 'M7 4v16 M3 8l4-4 4 4 M17 20V4 M13 16l4 4 4-4',
  cog: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z',

  // 信息 / 状态点
  info: 'M12 8h.01 M11 12h1v4h1 M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z',
  warning: 'M12 3l10 18H2L12 3Z M12 10v4 M12 18h.01',
  danger: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z M12 8v4 M12 16h.01',
  bell: 'M6 8a6 6 0 1 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9Z M10 21a2 2 0 0 0 4 0',
  star: 'M12 3l3 6 6 .9-4.5 4.4 1 6.7L12 18l-5.5 3 1-6.7L3 9.9l6-.9L12 3Z',
  flag: 'M5 21V4 M5 4h13l-2 5 2 5H5',
  clock: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z M12 6v6l4 2',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',

  // 业务语义
  cart: 'M3 4h2l3 12h11l3-9H6 M9 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z M18 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z',
  box: 'M3 7l9-5 9 5-9 5-9-5Z M3 7v10l9 5 9-5V7 M12 12v10',
  truck: 'M3 7h11v8H3z M14 10h4l3 4v1h-7 M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z M17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z',
  shield: 'M12 2l9 4v6c0 5-4 9-9 10-5-1-9-5-9-10V6l9-4Z M9 12l2 2 4-4',
  scale: 'M12 3v18 M6 7h12 M6 7l-3 7a3 3 0 0 0 6 0L6 7Z M18 7l-3 7a3 3 0 0 0 6 0L18 7Z',
  handshake: 'M11 17l2-2 2 2 4-4-2-2-2 2-4-4-2 2-4-4-2 2 4 4 2-2 M3 12l4-4 4 4 M21 12l-4 4-4-4',
  calculator: 'M4 4h16v16H4z M8 8h8 M8 12h.01 M12 12h.01 M16 12h.01 M8 16h.01 M12 16h.01 M16 16h.01',
  list: 'M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01',

  // 系统 / 菜单
  menu: 'M4 6h16 M4 12h16 M4 18h16',
  close: 'M18 6L6 18 M6 6l12 12',
  more: 'M5 12h.01 M12 12h.01 M19 12h.01',
  moreH: 'M5 12h14',
  panelLeft: 'M3 5h18v14H3z M9 5v14',
  sidebar: 'M5 4h14v16H5z M9 4v16',
  stop: 'M6 6h12v12H6z',
  send: 'M22 2 11 13 M22 2l-7 20-4-9-9-4 20-7Z',
  mic: 'M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z M19 11a7 7 0 0 1-14 0 M12 18v4 M8 22h8',
  refreshCW: 'M3 12a9 9 0 0 1 15-6.7L21 8 M21 3v5h-5 M21 12a9 9 0 0 1-15 6.7L3 16 M3 21v-5h5',

  // 工作台 / 面板
  bubble: 'M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z',
  bubbleFill: 'M5 3h14a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3h-6l-4 4v-4H5a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3Z',
  checkmarkCircle: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z M8 12l3 3 5-6',
  docText: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z M14 3v5h5 M9 13h6 M9 17h6 M9 9h2',
  sliderH: 'M4 6h12 M4 12h6 M4 18h10 M18 6h.01 M14 12h.01 M16 18h.01',
  bolt: 'M13 2 4 14h7l-1 8 9-12h-7l1-8Z',

  // 详情 / 状态点
  dot: 'M12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z',
  spinner: 'M12 3a9 9 0 1 0 9 9',
  zap: 'M13 2 3 14h7l-1 8 11-14h-8l1-6Z',
  flame: 'M12 2c1 4 5 5 5 9a5 5 0 0 1-10 0c0-2 1-3 2-4-1 4 3 4 3 0 0-2-2-3 0-5Z',
  inbox: 'M3 13h5l2 3h4l2-3h5 M3 13l3-9h12l3 9 M3 13v6a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6',
  archive: 'M3 5h18v4H3z M5 9v10h14V9 M10 13h4',
  rocket: 'M5 19c0-3 1-5 3-7l4 4c-2 2-4 3-7 3Z M14 5l5 5 M19 4l1 1 M9 15l-2 4 4-2',
}

const path = computed(() => ICONS[props.name] || ICONS.dot)
</script>

<style scoped>
.app-icon {
  display: inline-block;
  flex-shrink: 0;
  vertical-align: middle;
  transition: color var(--transition-fast), transform var(--transition-fast);
}
</style>
