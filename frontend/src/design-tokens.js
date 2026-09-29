/**
 * 设计 Token（LobeChat 风格 · 紫罗兰渐变科研工作台）
 * 颜色规范：
 *  - 主色紫罗兰（操作/链接/选中）#7a5af8，品牌渐变 → #b166ff
 *  - 辅助品红（高级身份）#c05be8
 *  - 绿色（成功）#18a058
 *  - 橙色（提醒）#d97706
 *  - 红色（高风险/失败）#e5484d
 *  - 灰色（禁用/未执行）#9b9aa7
 * 视觉语言：大圆角、通透浅色底、用户消息紫罗兰气泡、渐变主按钮。
 */

export const tokens = {
  color: {
    primary: '#7a5af8',
    primaryHover: '#6a48f0',
    primaryPressed: '#5b3ee0',
    primarySoft: 'rgba(122, 90, 248, 0.12)',
    primarySoftStrong: 'rgba(122, 90, 248, 0.20)',
    brandGrad: 'linear-gradient(135deg, #7a5af8 0%, #b166ff 100%)',
    accent: '#c05be8',
    accentSoft: 'rgba(192, 91, 232, 0.10)',
    success: '#18a058',
    successBright: '#2ecc71',
    successSoft: 'rgba(46, 204, 113, 0.14)',
    warning: '#d97706',
    warningBright: '#ffb020',
    warningSoft: 'rgba(255, 176, 10, 0.15)',
    danger: '#e5484d',
    dangerBright: '#ff5d5d',
    dangerSoft: 'rgba(255, 93, 93, 0.13)',
    muted: '#9b9aa7',
    mutedSoft: 'rgba(155, 154, 167, 0.12)',
    bg: '#f4f2fa',
    surface: '#ffffff',
    surface2: '#faf9fd',
    surfaceAlt: '#f6f4fb',
    border: 'rgba(58, 48, 108, 0.10)',
    borderLight: 'rgba(58, 48, 108, 0.05)',
    borderStrong: 'rgba(58, 48, 108, 0.16)',
    text: '#241f3a',
    textSecondary: '#55516b',
    textTertiary: '#908ca3',
  },
  radius: {
    xs: '6px',
    sm: '10px',
    md: '14px',
    lg: '18px',
    xl: '24px',
    xxl: '28px',
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
