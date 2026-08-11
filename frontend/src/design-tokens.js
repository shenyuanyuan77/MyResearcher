/**
 * 设计 Token（企业级 B 端 SaaS）
 * 阶段 6：替换原 ChatGPT 风格的 CSS 变量为更克制的 B 端规范。
 * 颜色规范：
 *  - 主色蓝（操作/链接）#2563eb
 *  - 辅助紫（高级身份）#7c3aed
 *  - 绿色（成功）#16a34a
 *  - 橙色（提醒）#d97706
 *  - 红色（高风险/失败）#dc2626
 *  - 灰色（禁用/未执行）#94a3b8
 * 严禁：渐变、玻璃拟态、Emoji 作为正式图标。
 */

export const tokens = {
  color: {
    primary: '#007AFF',
    primaryHover: '#0064d1',
    primaryPressed: '#004fa3',
    primarySoft: 'rgba(0, 122, 255, 0.12)',
    primarySoftStrong: 'rgba(0, 122, 255, 0.20)',
    accent: '#7c3aed',
    accentSoft: 'rgba(124, 58, 237, 0.10)',
    success: '#1a7f37',
    successBright: '#30d158',
    successSoft: 'rgba(48, 209, 88, 0.14)',
    warning: '#b25000',
    warningBright: '#ff9f0a',
    warningSoft: 'rgba(255, 159, 10, 0.15)',
    danger: '#c1271f',
    dangerBright: '#ff453a',
    dangerSoft: 'rgba(255, 69, 58, 0.13)',
    muted: '#94a3b8',
    mutedSoft: 'rgba(148, 163, 184, 0.12)',
    bg: '#f5f5f7',
    surface: '#ffffff',
    surface2: '#fbfbfd',
    surfaceAlt: '#f2f2f7',
    border: 'rgba(0, 0, 0, 0.08)',
    borderLight: 'rgba(0, 0, 0, 0.04)',
    borderStrong: 'rgba(0, 0, 0, 0.14)',
    text: '#1d1d1f',
    textSecondary: '#424245',
    textTertiary: '#86868b',
  },
  radius: {
    xs: '6px',
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '20px',
    xxl: '24px',
    pill: '999px',
  },
  shadow: {
    xs: '0 1px 2px rgba(0, 0, 0, 0.04)',
    sm: '0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04)',
    md: '0 4px 16px rgba(0, 0, 0, 0.08), 0 1px 4px rgba(0, 0, 0, 0.04)',
    lg: '0 12px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.06)',
    xl: '0 24px 64px rgba(0, 0, 0, 0.16), 0 4px 16px rgba(0, 0, 0, 0.08)',
  },
  typography: {
    display: 'var(--font-display)',
    body: 'var(--font-body)',
    mono: 'var(--font-mono)',
    hero: '40px',
    h1: '28px',
    h2: '22px',
    bodySize: '15px',
    caption: '13px',
    mini: '11px',
  },
  spacing: {
    aside: '248px',
    context: '320px',
    header: '56px',
    mainPad: '24px',
    rowHeight: '46px',
  },
  motion: {
    ios: 'cubic-bezier(.32, .72, 0, 1)',
    spring: 'cubic-bezier(.22, 1, .36, 1)',
    springStrong: 'cubic-bezier(.34, 1.56, .64, 1)',
    fast: '0.16s',
    normal: '0.28s',
    slow: '0.45s',
  },
  transition: '0.28s cubic-bezier(.22, 1, .36, 1)',
}

/**
 * 角色 → 显示样式映射（避免到处散写 if）。
 */
export const roleMeta = {
  admin:      { label: '管理员', color: 'var(--c-accent)', bg: 'var(--c-accent-soft)' },
  researcher: { label: '研究员', color: 'var(--c-primary)', bg: 'var(--c-primary-soft)' },
  student:    { label: '研究生', color: 'var(--c-primary)', bg: 'var(--c-primary-soft)' },
  viewer:     { label: '观察者', color: 'var(--c-text-secondary)', bg: 'var(--c-muted-soft)' },
}

/**
 * 任务状态 → 显示样式映射（与 task_state.py 文本一致）。
 */
export const taskStateMeta = {
  draft:                     { label: '草稿',         cls: 'muted',   icon: '○' },
  planning:                  { label: '规划中',       cls: 'primary', icon: '◐' },
  waiting_for_parameters:    { label: '待补全参数',   cls: 'warning', icon: '!' },
  ready:                     { label: '计划就绪',     cls: 'primary', icon: '◇' },
  waiting_for_confirmation:  { label: '等待用户确认', cls: 'warning', icon: '?' },
  waiting_for_approval:      { label: '等待审批',     cls: 'warning', icon: '⚖' },
  executing:                 { label: '执行中',       cls: 'primary', icon: '›' },
  succeeded:                 { label: '已完成',       cls: 'success', icon: '✓' },
  failed:                    { label: '失败',         cls: 'danger',  icon: '×' },
  cancelled:                 { label: '已取消',       cls: 'muted',   icon: '−' },
}

/**
 * 意图 → 中文（与 task_state.py 对齐）。
 */
export const intentMeta = {
  topic_radar:    '方向构建',
  paper_search:   '文献检索',
  paper_distill:  '文献精读',
  author_profile: '学者透视',
  cross_search:   '跨界推演',
  review:         'AI 审稿',
  quick_lookup:   '快速查询',
  deep_analysis:  '深度分析',
  chat:           '闲聊',
}

/**
 * 工具状态图标映射（不使用 Emoji）。
 */
export const toolStatusMeta = {
  calling: { label: '调用中', cls: 'primary', glyph: '›' },
  done:    { label: '完成',   cls: 'success', glyph: '✓' },
  error:   { label: '失败',   cls: 'danger',  glyph: '×' },
  skipped: { label: '跳过',   cls: 'muted',   glyph: '−' },
}

/**
 *Agent 执行计划步骤状态（与 LangGraph 节点状态一致）。
 */
export const planStepMeta = {
  pending: { label: '等待', cls: 'muted',   glyph: '○' },
  running: {label: '执行中', cls: 'primary', glyph: '›' },
  done:    { label: '已完成', cls: 'success', glyph: '✓' },
  failed:{ label: '失败',   cls: 'danger',  glyph: '×' },
  skipped: { label: '已跳过', cls: 'muted',   glyph: '−' },
}

/**
 * Agent 任务会话状态（与侧边栏分组标签对齐）。
 */
export const sessionStateMeta = {
  recent: { label: '最近任务', icon: '◐' },
  pending_approval: { label: '待审批', icon: '⚖' },
  completed: { label: '已完成', icon: '✓' },
  failed: { label: '失败', icon: '×' },
  starred: { label: '收藏', icon: '☆' },
}

/**
 * 风险/可行性等级映射（跨界推演可行性、审稿严重程度等共用）。
 */
export const riskLevelMeta = {
  high:       { label: '高',     cls: 'danger',  color: 'var(--c-danger)' },
  medium:     { label: '中',     cls: 'warning', color: 'var(--c-warning)' },
  low:        { label: '低',     cls: 'success', color: 'var(--c-success)' },
  conditional:{ label: '有条件', cls: 'warning', color: 'var(--c-warning)' },
  full:       { label: '完全',   cls: 'success', color: 'var(--c-success)' },
}
