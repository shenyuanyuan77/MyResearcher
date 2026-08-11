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
    primary: '#2563eb',
    primaryHover: '#1d4ed8',
    primarySoft: 'rgba(37, 99, 235, 0.08)',
    accent: '#7c3aed',
    accentSoft: 'rgba(124, 58, 237, 0.08)',
    success: '#16a34a',
    successSoft: 'rgba(22, 163, 74, 0.08)',
    warning: '#d97706',
    warningSoft: 'rgba(217, 119, 6, 0.08)',
    danger: '#dc2626',
    dangerSoft: 'rgba(220, 38, 38, 0.08)',
    muted: '#94a3b8',
    mutedSoft: 'rgba(148, 163, 184, 0.10)',
    // 中性
    bg: '#f8fafc',           // 页面背景（浅灰）
    surface: '#ffffff',      // 卡片白
    surfaceAlt: '#f1f5f9',
    border: '#e2e8f0',
    borderLight: '#f1f5f9',
    text: '#0f172a',         // 主体文本：高对比
    textSecondary: '#334155',
    textTertiary: '#64748b',
  },
  radius: {
    sm: '6px',
    md: '8px',
    lg: '12px',
  },
  shadow: {
    sm: '0 1px 2px rgba(15, 23, 42, 0.04)',
    md: '0 2px 8px rgba(15, 23, 42, 0.06)',
    lg: '0 4px 16px rgba(15, 23, 42, 0.08)',
  },
spacing: {
    aside: '240px',         // 左侧导航
    context: '320px',       // 右侧上下文面板（可折叠 → 0px）
    header: '56px',         // 中间顶部 Header
    mainPad: '24px',
    rowHeight: '46px',      //表格行高
  },
  transition: '0.18s cubic-bezier(0.4, 0, 0.2, 1)',
}

/**
 * 角色 → 显示样式映射（避免到处散写 if）。
 */
export const roleMeta = {
  admin:    { label: '管理员', color: '#7c3aed', bg: 'rgba(124, 58, 237, 0.10)' },
  approver: { label: '审批人', color: '#d97706', bg: 'rgba(217, 119, 6, 0.10)' },
  buyer:    { label: '采购员', color: '#2563eb', bg: 'rgba(37, 99, 235, 0.10)' },
  viewer:   { label: '观察者', color: '#475569', bg: 'rgba(71, 85, 105, 0.10)' },
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
  quick_lookup:    '快速查询',
  deep_analysis:   '深度分析',
  order:           '采购订单',
  shortage:        '缺料分析',
  purchase_request:'采购申请',
  substitute:      '替代料推荐',
  price_compare:   '供应商比价',
  inventory_risk:  '库存风险综合',
  order_anomaly:   '订单异常识别',
  chat:            '闲聊',
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
 * 风险等级映射（供应商/MSL/订单异常共用）。
 */
export const riskLevelMeta = {
  high:       { label: '高风险', cls: 'danger',  color: '#dc2626' },
  medium:     { label: '中风险', cls: 'warning', color: '#d97706' },
  low:        { label: '低风险', cls: 'success', color: '#16a34a' },
  conditional:{ label: '条件',   cls: 'warning', color: '#d97706' },
  full:       { label: '完全',   cls: 'success', color: '#16a34a' },
}
