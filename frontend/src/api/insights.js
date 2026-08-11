/**
 * 研途智探AI · 欢迎页 Insights（存根）
 *
 * 研途场景无审批/订单/库存预警，提供空实现保持兼容。
 * 后续如需「待精读文献/待溯源DOI」等摘要，在此扩展。
 */

/**
 * 拉取欢迎页所需的「待处理」摘要数字。
 * 研途 MVP 无后端摘要接口，返回空对象。
 */
export async function fetchPendingSummary() {
  return {
    pendingReviews: 0,
    pendingTrace: 0,
    hotPapers: 0,
    crossIdeas: 0,
  }
}

/**
 * 欢迎页快捷入口（研途主题）。
 */
export function getQuickEntries() {
  return [
    { key: 'search', label: '检索最新文献', message: '帮我检索 RAG 领域最新高引文献' },
    { key: 'author', label: '学者画像', message: '查 Yann LeCun 的学者画像' },
    { key: 'cross', label: '跨界推演', message: '推演大模型×量子计算的融合可行性' },
    { key: 'review', label: 'AI 审稿', message: '帮我审稿这段论文摘要' },
  ]
}
