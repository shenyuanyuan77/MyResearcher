/**
 * markdown 重整单元测试
 * 用法: node frontend/src/utils/markdownTables.test.js
 */
import MarkdownIt from 'markdown-it'
import { normalizeMarkdown, fixMarkdownTables } from './markdownTables.js'
import { reportTablesHealthy, findTableHealthIssues } from './reportTableCanon.js'

const md = new MarkdownIt({ breaks: true, html: true })
md.enable(['table'])

const prose =
  '>所有光板均符合 RoHS，效期180~365天，MSL为 N/A（光板不含潮敏器件）。需要查看某个物料的库存明细或替代料可告诉我。'

const cases = [
  {
    name: 'emdash-collapsed',
    expectTr: 4,
    sample: `查到 **3款 PCB光板物料**：|名称 | MPN |制造商 |规格 | MOQ |交期 |单价 | ROHS | |—|—|—|—|—|—|—|—|| 4层PCB光板 | PCB-4L-10080 | 深南电路 | 1.6mm 1oz 100x80mm | 10 | 8天 | ¥18.50 | ✅ | 2层PCB光板 | PCB-2L-5050 | 崇达技术 | 1.6mm 1oz 50x50mm | 10 | 4天 | ¥3.20 | ✅ | 4层PCB光板备选厂 | PCB-4L-10080-B | 华秋电子 | 1.6mm 1oz 100x80mm | 10 | 4天 | ¥16.80 | ✅ |4层板有两个版本：深南电路（主供）和华秋电子（备选）。`,
  },
  {
    name: 'prose-row-peeled',
    expectTr: 8,
    expectOutside: '所有光板均符合',
    sample: `共查到 7 款：\n\n|名称|MPN|\n|---|---|\n|2层PCB光板|PCB-2L-001|\n|铝基板 LED|ALPCB-LED-001|\n|4层PCB光板|PCB-4L-002|\n|4层PCB光板(备选)|PCB-4L-002B|\n|4层沉金PCB|PCB-4L-ENIG|\n|6层HDI光板|PCB-6L-HDI|\n|8层多层板|PCB-8L-001|\n|${prose}|`,
  },
  {
    name: 'report-heading',
    check: (fixed, html) =>
      fixed.includes('# 📊') &&
      fixed.includes('> 分析对象') &&
      fixed.includes('## 一、供应商概览') &&
      html.includes('<h1') &&
      html.includes('<blockquote'),
    sample: `—# 📊覆铜板采购深度分析报告>分析对象：采购业务部门 |统计周期：2025-01-01 ~2026-07-21 |报告时间：2026-07-21—##一、供应商概览覆铜板品类主要由 2家供应商覆盖，均以生益科技为主：`,
  },
  {
    name: 'report-mashed',
    check: (fixed, html) =>
      fixed.includes('## 二、覆铜板物料清单') &&
      fixed.includes('|物料编码|') &&
      fixed.includes('> ⚠️') &&
      !fixed.split('\n').some((l) => l.startsWith('|') && l.includes('1688比板多多')) &&
      html.includes('<table') &&
      html.includes('<h2'),
    sample: `关键发现：板多多占70.2%。一##二、覆铜板物料清单###2.1核心物料明细物料编码 名称 MPN 制造商 规格 采购单价 建议零售价 MOQ 交期(天) 效期(天) RoHS 无卤 --------- ------ ----- -------- ------ -------- ---------- --- -------- -------- ---- ---- CCL-FR4-1.6 FR-4覆铜板1.6mm CCL-FR4-1.6 生益科技 1.6mm/35μm ¥85.00 ¥98.00 50 3 365 ✅ ❌CCL-FR4-0.8 FR-4覆铜板0.8mm CCL-FR4-0.8 生益科技 0.8mm/35μm ¥72.00 ¥85.00 50 3 365 ✅ ✅###2.2价格对比分析规格 板多多单价 1688单价 价差 降幅 风险等级 ------ ---------- ---------- ------ ------ ---------- FR41.6mm ¥85.00 ¥78.00 -¥7.00 -8.2% ⚠️注意 FR40.8mm ¥72.00 - - - 无替代 高TG ¥125.00 - - - 无替代> ⚠️ 1688比板多多便宜8.2%。一##三、采购趋势分析###3.1覆铜板品类整体采购额统计期内覆铜板与基材总采购额: ¥404,610.37`,
  },
  {
    name: 'preserve-good-report',
    check: (fixed) =>
      fixed.includes('## 一、概览') &&
      fixed.includes('|板多多|100|') &&
      !/^#\s*$/m.test(fixed),
    sample: `# 正常报告\n\n## 一、概览\n\n|供应商|金额|\n|---|---|\n|板多多|100|\n\n## 二、结论\n\n没问题。`,
  },
  {
    name: 'dedupe-section-67-and-trim-orphan',
    check: (fixed) => {
      const liu = (fixed.match(/^## 六、/gm) || []).length
      const qi = (fixed.match(/^## 七、/gm) || []).length
      const endsOk = /是否需要将此报告下载[^\n]*$/.test(fixed.trim())
      const noOrphan = !fixed.includes('总库存') && !fixed.includes('供应结构')
      const gluedGone = !fixed.includes('|>所有')
      const proseOut =
        fixed.includes('所有覆铜板 A批号') &&
        !fixed.split('\n').some((l) => l.startsWith('|') && l.includes('所有覆铜板'))
      return liu === 1 && qi === 1 && endsOk && noOrphan && gluedGone && proseOut
    },
    sample: `## 三、库存与效期风险

### 3.3 近效期预警（60天内）

|物料 |批号 |库存量 |到期日 |剩余天数 |风险等级 |
|------|------|--------|--------|----------|----------|
| CCL-FR4-1.6 | LOT-25-A |11 |2026-10-18 |89 | 🟢安全 |
| CCL-FR4-1.6-1688 | LOT-71-A |284 |2026-10-18 |89 | 🟢安全 |>所有覆铜板 A批号效期均在89天后到期。

## 六、采购趋势

趋势图。

## 七、结论

1. **补货**：立刻。

---

是否需要将此报告下载到本地？回复「下载」即可。保存

覆铜板大类总库存（张） 955 **供应结构**：- **板多多（A级信用）**：70.2%**风险**：- CCL 预警
## 六、采购趋势

趋势图。

## 七、结论

1. **补货**：立刻。

---

是否需要将此报告下载到本地？回复「下载」即可。保存

覆铜板大类总库存（张） 955 **供应结构**：- 重复残片`,
  },
  {
    name: 'no-tail-duplication-on-collapsed-table',
    check: (fixed) => {
      const liu = (fixed.match(/^## 六、/gm) || []).length
      return liu === 1 && fixed.includes('|深南|') && fixed.includes('## 六、采购趋势')
    },
    sample: `查到物料：|名称|厂商|\n|---|---||深南|A||华秋|B|

## 六、采购趋势

正文一次。

## 七、结论

结束。

是否需要将此报告下载到本地？回复「下载」即可。`,
  },
  {
    name: 'chart-and-table-separated',
    check: (fixed) => {
      const imgIdx = fixed.indexOf('![累计采购量]')
      const tableIdx = fixed.indexOf('|物料 |累计采购量')
      const between = fixed.slice(imgIdx, tableIdx)
      return (
        imgIdx >= 0 &&
        tableIdx > imgIdx &&
        between.includes('](') &&
        /\n\n\|物料/.test(fixed) &&
        !/\]\([^)]+\)\|物料/.test(fixed)
      )
    },
    sample: `### 6.1 覆铜板品类采购量对比![累计采购量](https://mdn.alipayobjects.com/one_clip/afts/img/x.png)|物料 |累计采购量 (张) |累计金额 (¥) |
|------|-----------------|--------------|
| CCL-FR4-1.6 |1,214 |111,984 |`,
  },
  {
    name: 'section-not-inside-supplier-table',
    check: (fixed, html) => {
      const broken = fixed.split('\n').some(
        (l) => l.startsWith('|') && l.includes('###') && l.includes('月度价格')
      )
      return (
        !broken &&
        fixed.includes('### 月度价格走势分析') &&
        html.includes('<h3') &&
        fixed.includes('|板多多|')
      )
    },
    sample: `## 四、供应商分析

|供应商 |角色 |信用评级 |
|---|---|---|
|板多多|合作主供|A|
|1688工业品|对比备选|B|
|###月度价格走势分析（FR41.6mm双渠道）**板多多 CCL-FR4-1.6成交价趋势**：|订单日期|数量 (张)|
|----------|-----------|--------------|
|Order#49|58|82.59|`,
  },
  {
    name: 'order-dump-collapsed-to-plain-speech',
    check: (fixed) =>
      !/Order#49/.test(fixed) &&
      (fixed.includes('趋势研判') || /从 ¥\d/.test(fixed) || /大约从 ¥/.test(fixed)),
    sample: `### 月度价格走势分析

|订单日期|数量 (张)|成交单价 (¥)|
|----------|-----------|--------------|
|Order#49|58|82.59|
|Order#69|54|90.87|
|Order#247|150|97.13|

> **趋势研判**：板多多从 ~¥82涨至 ~¥97。`,
  },
  {
    name: 'supply-risk-to-tables',
    check: (fixed, html) =>
      fixed.includes('| 供应商 |') &&
      fixed.includes('| 序号 | 风险说明 |') &&
      fixed.includes('70.2%') &&
      (html.match(/<table/g) || []).length >= 2,
    sample: `## 一、摘要

说明。

|指标 |数值 |
|------|------|
|SKU |4 |**供应结构**：-板多多（PCB原材料垂直平台）：3个核心料，金额 ¥259,579，占比约70.2%（主供，信用评级 A）-阿里巴巴1688工业品：1个料（FR41.6mm散剪比价），金额 ¥110,310，占比约29.8%（备选，信用评级 B）**风险要点**：-库存缺口-高TG单源

---

## 二、物料清单
`,
  },
  {
    name: 'merge-orphan-supplier-row',
    check: (fixed) => {
      const row = fixed.split('\n').find((l) => l.includes('板多多') && l.includes('259,579'))
      return row && row.startsWith('|') && row.includes('合作主供') && row.includes('70.2%')
    },
    sample: `### 4.1 供应商分布

|供应商 |角色 |信用评级 |采购金额 (¥) |占比 |
|--------|------|----------|--------------|------|
|板多多（PCB原材料垂直平台）

|合作主供 | A |259,579 |70.2% |
|阿里巴巴1688工业品 |对比备选 | B |110,310 |29.8% |
`,
  },
  {
    name: 'supplier-profile-comparison-table',
    check: (fixed) =>
      fixed.includes('| 对比项 |') &&
      fixed.includes('板多多') &&
      fixed.includes('1688') &&
      !/\*\*板多多（SUP-BDD）-主供/.test(fixed),
    sample: `### 4.2 供应商画像**板多多（SUP-BDD）-主供，金额占比七成**-覆铜板品类核心渠道，涵盖 FR41.6mm /0.8mm /高 TG三款-交期整体短：FR41.6mm仅3天-信用评级 A，品质稳定-劣势：高 TG无备选**1688工业品（SUP-1688）-散剪比价渠道，金额占比近三成**-仅供应 FR41.6mm散剪型-交期最短仅2天-信用评级 B-优势：无卤认证 ✅

---

## 五、比价
`,
  },
  {
    name: 'conclusion-linebreak-and-action-table',
    check: (fixed) =>
      /结论与行动建议/.test(fixed) &&
      fixed.includes('| 序号 | 事项 |') &&
      !/行动建议1\./.test(fixed),
    sample: `## 七、结论

与行动建议1. **补充 FR41.6mm库存（本周执行）**：当前库存26低于安全线33，优先补货。
2. **高 TG拓展备选（高优先）**：引入第二家供应商。
3. **效期出库（中优先）**：制定FIFO计划。

---

是否需要将此报告下载到本地？回复「下载」即可。
`,
  },
  {
    name: 'normalize-idempotent',
    check: (fixed) => {
      const again = normalizeMarkdown(fixed)
      const third = normalizeMarkdown(again)
      const riskOk = !/\/ 序号 \//.test(again) && (again.match(/\*\*风险要点\*\*/g) || []).length <= 2
      const noSlashRow = !again.split('\n').some((l) => /^\/\s*.+\s*\/$/.test(l.trim()))
      const profileOk = !/对比项\|\|对比项/.test(again)
      const subOk =
        /CCL-FR4-1\.6（板多多）/.test(again) &&
        /CCL-FR4-1\.6-1688/.test(again) &&
        !/\|\s*CCL-FR4-1\.6（板多多）\s*\|\s*$/m.test(again)
      // 硬性：normalize 必须幂等，否则前端每次渲染都会越修越坏
      return (
        again === fixed &&
        third === fixed &&
        again.includes('| 序号 | 风险说明 |') &&
        riskOk &&
        noSlashRow &&
        profileOk &&
        subOk &&
        again.includes('70.2%')
      )
    },
    sample: `## 一、摘要

说明。

|指标 |数值 |
|------|------|
|SKU |4 |**供应结构**：-板多多（PCB原材料垂直平台）：3个核心料，金额 ¥259,579，占比约70.2%（主供，信用评级 A）-阿里巴巴1688工业品：1个料（FR41.6mm散剪比价），金额 ¥110,310，占比约29.8%（备选，信用评级 B）**风险要点**：-覆铜板 FR41.6mm当前库存仅26张，低于安全库存33，存在缺口-高 TG覆铜板无替代料储备，依赖板多多单一渠道- FR40.8mm无卤认证 ✅

### 4.2 供应商画像**板多多（SUP-BDD）-主供，金额占比七成**-覆铜板品类核心渠道，涵盖三款-交期短-信用评级 A-劣势：高TG单源**1688工业品（SUP-1688）-散剪比价，占比近三成**-仅供应散剪-交期2天-信用评级 B-优势：无卤

### 5.2 替代料情况

|主物料 |替代料 |关系 |
|--------|--------|------|
| CCL-FR4-1.6（板多多）

| CCL-FR4-1.6-1688（1688） |已建立双向替代，优先级2 |- **高 TG**当前无替代料。

## 七、结论
与行动建议1. **补货（本周）**：立刻。
2. **寻源（高优先）**：引入第二家。

---

是否需要将此报告下载到本地？回复「下载」即可。
`,
  },
  {
    name: 'supply-slash-in-cell-preserved',
    check: (fixed) =>
      fixed.includes('板多多（PCB原材料垂直平台）') &&
      /CCL-FR4-1\.6/.test(fixed) &&
      /72\.7%/.test(fixed) &&
      !/^\|供应商\|$/m.test(fixed) &&
      (fixed.match(/\| 主供 \|/g) || fixed.match(/\|主供\|/g) || []).length >= 0 &&
      fixed.split('\n').some((l) => l.includes('板多多') && l.includes('72.7%')),
    sample: `**供应结构**

| 供应商 | 物料 | 金额 (¥) | 占比 | 角色 | 信用 |
|--------|------|----------|------|------|------|
| 板多多（PCB原材料垂直平台） | CCL-FR4-1.6 / FR4-0.8 / HIGH-TG / PP-7628 | 294,297.88 | 72.7% | 主供 | A |
| 阿里巴巴1688工业品 | CCL-FR4-1.6-1688 | 110,309.70 | 27.3% | 备选/比价 | B |
`,
  },
  {
    name: 'glued-numbered-points-break',
    check: (fixed) =>
      /\n2\.\s+\*\*FR41\.6mm/.test(fixed) &&
      /\n3\.\s+\*\*所有覆铜板/.test(fixed) &&
      /\n4\.\s+FR41\.6mm价格/.test(fixed),
    sample: `半固化片7628无替代料，单源依赖板多多，当前库存仅15张（安全库存25），处于预警状态 2 **FR41.6mm板多多库存26张 < 安全库存33**，属于库存预警；近效期批次 LOT-25-A（11张，2026-10-18到期） 3 **所有覆铜板 SKU仅2家供应商**，板多多占七成以上，集中度偏高 4 FR41.6mm价格从 ¥82.59持续攀升至 ¥97.63，涨幅 **18.2%**，趋势未扭转 —
`,
  },
  {
    name: 'orphan-action-row6-pulled-in',
    check: (fixed) =>
      /\| 6 \|/.test(fixed) &&
      /效期追踪机制/.test(fixed) &&
      !/^6\s+效期追踪机制/m.test(fixed),
    sample: `## 八、结论与行动建议

| 序号 | 事项 | 优先级 | 建议 |
|------|------|--------|------|
| 5 | 长期优化供应结构 | 🟢中 | 目标降至60%以下 |

6 效期追踪机制 🟢中 覆铜板统一效期180天，建议引入「效期90天自动预警->60天自动排产->30天强制消耗」三级机制 —

---
`,
  },
  {
    name: 'metrics-table-risks-split',
    check: (fixed) =>
      fixed.includes('**风险要点**') &&
      fixed.includes('| 序号 | 风险说明 |') &&
      /半固化片7628/.test(fixed) &&
      /高TG覆铜板无替代料/.test(fixed) &&
      fixed.includes('| 指标 | 数值 |') &&
      /订单笔数/.test(fixed) &&
      /\| 4 \|/.test(fixed),
    sample: `## 一、摘要

覆铜板与基材是企业 PCB生产的第二大采购品类，累计44笔订单、金额 ¥404,610，占总采购额16.7%。

|指标 |数值 |
|---|---|
|1|半固化片7628（PP-7628）当前库存15张，低于安全库存25张，且 LOT-27-A将在2026-09-03到期|
|高TG覆铜板无替代料，且单源供应（仅板多多），缺料风险较高|3|
|半固化片供货交期波动大：PP-2116交期9天，远超其他品类|---|

覆铜板 FR41.6mm（板多多）价格从 ¥82.59持续上行至 ¥97.63，18个月涨幅18.2%
---
`,
  },
  {
    name: 'incomplete-leadtime-row-merged',
    check: (fixed) => {
      const okRow = fixed
        .split('\n')
        .some((l) => /交期/.test(l) && /3天/.test(l) && /2天/.test(l) && l.includes('|'))
      const headingOk = /### 4\.1 覆铜板供应商对比/.test(fixed)
      const noOrphan = !/^\|3天\|2天\|$/m.test(fixed)
      return okRow && headingOk && noOrphan && fixed === normalizeMarkdown(fixed)
    },
    sample: `### 4.1 覆铜

板供应商对比

|对比项 |板多多 |1688工业品 |
|--------|--------|-------------|
|供货物料数 |5 |1（FR41.6mm替代） |
|覆铜板采购额占比 |72.74% |27.26% |
|信用评级 | A | B |
|交期（FR41.6mm）

|3天|2天|
|---|---|
|1688价格优势|- 便宜约10%|

**解读**：板多多主供。
`,
  },
]

cases.push({
  name: 'vertical supply header dump + glued risks',
  sample: `**供应结构**|供应商|
|涉及物料|金额 (¥)|
|占比|角色|
|信用||
|--------|----------|
|----------|------|
|------|------|
|板多多（PCB原材料垂直平台）||
|CCL-FR4-1.6、FR4-0.8、HIGH-TG、PP-7628|294,298|
|72.7%|主供|
|A||
|阿里巴巴1688工业品|CCL-FR4-1.6-1688|
|110,310|27.3%|
|备选/比价|B|

**风险要点**|序号|
|风险说明||
|------|----------|
|1||

**半固化片 PP-7628无替代料**，仅板多多单源供应，当前库存15张、安全库存25，处于低库存预警 2 **CCL-FR4-1.6 (板多多)库存低于安全线**，当前26张 <33安全值
`,
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const supplyOk =
      /\| 板多多[^|]*\|[^|]*CCL-FR4-1\.6[^|]*\|[^|]*294,298[^|]*\|[^|]*72\.7%[^|]*\|[^|]*主供[^|]*\|[^|]*A/.test(
        fixed
      ) &&
      /\| 阿里巴巴1688工业品 \| CCL-FR4-1\.6-1688 \| 110,310 \| 27\.3% \| 备选\/比价 \| B \|/.test(fixed)
    const riskOk =
      /\| 1 \| 半固化片 PP-7628/.test(fixed) &&
      /\| 2 \| CCL-FR4-1\.6 \(板多多\)库存低于安全线/.test(fixed) &&
      !/\| 1 \|[^|]*2\.\s*\*\*CCL/.test(fixed) &&
      !fixed.split('\n').some((l) => /^2\.\s*\*\*CCL/.test(l.trim())) &&
      !/\|\n\n\| 2 \|/.test(fixed)
    return supplyOk && riskOk && again === fixed
  },
})

cases.push({
  name: 'mangled-risk-intrusion-rows',
  sample: `**风险要点**

| 序号 | 风险说明 |
|------|----------|
| 1 | 半固化片 PP-7628无替代料**，仅板多多单源供应，当前库存15张、安全库存25，处于低库存预警 |
2. **CCL |
| 2 | FR4-1.6 (板多多)库存低于安全线**，当前26张 <33安全值，且受涨价影响
3. **FR40.8mm和 HIGH-TG均无替代料**，依赖板多多单渠道
4. **FR41.6mm价格持续上涨**，板多多渠道从 ¥82.59涨至 ¥97.63（+18.2%） 5. |
**近效期风险集中**：多个批次制造日期2026-06-20，距今仅30天寿命窗口 ---

## 二、物料清单
`,
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    return (
      again === fixed &&
      /CCL-FR4-1\.6 \(板多多\)库存低于安全线/.test(fixed) &&
      /近效期风险集中/.test(fixed) &&
      !fixed.split('\n').some((l) => /^2\.\s*\*\*CCL/.test(l.trim()))
    )
  },
})

cases.push({
  name: 'collapsed-prefs-double-pipe-table',
  sample:
    '你的偏好文件尚未创建。按默认偏好：|项目 |默认值 ||------|--------||输出格式 |图表 (chart) ||图表类型 |柱状图 (bar) ||货币 | CNY ||语言 |简体中文 ||常用供应商 |无 ||历史查询 |无 |需要我按你的习惯更新这些偏好吗？',
  check: (fixed, html) => {
    const raw =
      '你的偏好文件尚未创建。按默认偏好：|项目 |默认值 ||------|--------||输出格式 |图表 (chart) ||图表类型 |柱状图 (bar) ||货币 | CNY ||语言 |简体中文 ||常用供应商 |无 ||历史查询 |无 |需要我按你的习惯更新这些偏好吗？'
    if (reportTablesHealthy(raw)) return false
    if (!findTableHealthIssues(raw).includes('collapsed_double_pipes')) return false
    return (
      html.includes('<table') &&
      fixed.includes('|输出格式') &&
      !fixed.includes('||------') &&
      fixed === normalizeMarkdown(fixed)
    )
  },
})

cases.push({
  name: 'list-supply-risk-to-canon-table',
  sample: `## 一、摘要

**供应结构**
- 板多多（PCB原材料垂直平台）：物料 CCL-FR4-1.6、FR4-0.8；金额 294,298；占比 72.7%；角色 主供；信用 A
- 阿里巴巴1688工业品：物料 CCL-FR4-1.6-1688；金额 110,310；占比 27.3%；角色 备选/比价；信用 B

**风险要点**
- 半固化片 PP-7628 无替代料，单源依赖
- CCL-FR4-1.6 库存低于安全线
`,
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    return (
      again === fixed &&
      /\| 板多多[^|]*\|[^|]*CCL-FR4-1\.6/.test(fixed) &&
      /\| 1 \| 半固化片 PP-7628/.test(fixed) &&
      /\| 2 \| CCL-FR4-1\.6/.test(fixed)
    )
  },
})

// 会话 29c712fa：伪份额风险 + 图粘供应标题 + 双风险块 + 行内 **日期** 不得截断/塌行
cases.push({
  name: 'session-dup-risk-fake-share-bold-date',
  sample: `## 一、摘要

关键数字：SKU 6，金额 ¥404,617.77。

**风险要点**

| 序号 | 风险说明 |
|------|----------|
| 1 | 1688工业品 ¥110,309.70（27.26%） |

![覆铜板与基材供应商金额占比](https://mdn.alipayobjects.com/one_clip/afts/img/ReLPSZTy2VMAAAAARaAAAAgAoEACAQFr/original)**供应结构**

| 供应商 | 物料 | 金额 (¥) | 占比 | 角色 | 信用 |
|------|------|----------|------|------|------|
| 板多多（PCB原材料垂直平台） | 5 | 294,308.07 | 72.74% | 合作主供 | A |
| 阿里巴巴1688工业品 | 1 | 110,309.70 | 27.26% | 对比备选 | B |

**风险要点**：|序号 |风险说明 |
|------|----------|
|1 |半固化片7628（PP-7628）当前库存15张，低于安全库存25张，缺口 -10；LOT-27-A（6张）将于 **2026-09-03**到期，仅剩约44天 |
|2 |半固化片2116（PP-2116）LOT-28-A（236张）同样于2026-09-03到期，虽库存充足但面临集中到期压力 |
|3 |高TG覆铜板、FR40.8mm、半固化片7628/2116均无替代料，仅板多多单源供应，断供风险高 |
|4 |覆铜板 FR41.6mm（板多多）价格从约 ¥82.59持续上行至 ¥97.63，18个月涨幅约18.2% |
|5 |PP-2116交期9天，远超覆铜板类物料（2~4天），备货窗口需提前 |

## 二、物料清单
`,
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const riskBlocks = fixed.match(/\*\*风险要点\*\*/g) || []
    const riskSection = fixed.slice(fixed.indexOf('**风险要点**'), fixed.indexOf('## 二'))
    const riskRows = (riskSection.match(/^\|\s*\d+\s*\|/gm) || []).length
    const noFakeShare = !/^\|\s*\d+\s*\|[^|\n]*¥110,309/m.test(riskSection)
    const imgDetached = !/\]\([^)]+\)[ \t]*\*\*/.test(fixed)
    return (
      again === fixed &&
      riskBlocks.length === 1 &&
      riskRows === 5 &&
      noFakeShare &&
      imgDetached &&
      /半固化片7628/.test(riskSection) &&
      /交期9天/.test(riskSection) &&
      findTableHealthIssues(fixed).length === 0 &&
      findTableHealthIssues(
        '![x](http://a.com/b)**供应结构**\n\n|a|b|\n|-|-|\n|1|2|'
      ).includes('image_glued_to_heading')
    )
  },
})

cases.push({
  name: 'price-trend-mashed-to-table',
  sample: `## 六、采购趋势

### 6.1 覆铜板价格趋势FR4 1.6mm（板多多）价格在18个月内稳步上行：-最低：2025-03 ¥82.59 →近期：2026-07 ¥97.63- 累计涨幅约18.2%，年均约12%高TG覆铜板相对稳定，波动在 ¥130.47~¥138.62之间。1688渠道的 FR4 1.6mm从 ¥76.30涨至 ¥93.36，涨幅22.4%，但整体仍比板多多便宜约10%。

### 6.2 月度采购额变化
`,
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const sec = fixed.slice(fixed.indexOf('### 6.1'), fixed.indexOf('### 6.2'))
    return (
      again === fixed &&
      /\| FR4 1\.6mm · 板多多 \|/.test(sec) &&
      /¥82\.59（2025-03）/.test(sec) &&
      /¥97\.63（2026-07）/.test(sec) &&
      /\*\*18\.2%\*\*/.test(sec) &&
      /\| FR4 1\.6mm · 1688 \|/.test(sec) &&
      /\| 高TG覆铜板 \|/.test(sec) &&
      !/稳步上行：-最低/.test(sec)
    )
  },
})

cases.push({
  name: 'dashboard-fake-cols-and-glued-trend',
  sample: `## 📊采购仪表盘

|指标 |数值 |
|---|---|
|物料总数|75|
|供应商数|6|

### 本月（2026-07）

指标

|数值||
|---|---|
|本月采购额|¥85,175.86|
|本月订单数|11|
|已完成订单|0|

### ⚠️预警

类型

|数量||
|---|---|
|---|---|
|列1|列2|
|---|---|
|2026-01|75,818.35|
|8|
|2026-02|135,087.40|
|8|
|2026-03|169,007.54|
|8|

**趋势小结：**4月峰值。

近效期批次 11
MSL开封超时 0 —

## 📈月度采购趋势 月份 采购额 (¥) 订单数
`,
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const noFake = !/\|?\s*列\s*[12]\s*\|/.test(fixed)
    const warnOk =
      /近效期批次/.test(fixed) &&
      /MSL开封超时/.test(fixed) &&
      !/预警[\s\S]{0,120}\| 2026-01 \|/.test(fixed)
    const trendOk =
      /\| 月份 \|/.test(fixed) &&
      /\| 2026-01 \|/.test(fixed) &&
      /¥75,818/.test(fixed) &&
      /\| 2026-01 \|[^|\n]*\| 8 \|/.test(fixed) &&
      !/月度采购趋势[ \t]+月份/.test(fixed)
    const monthKpi =
      /\| 指标 \|/.test(fixed) &&
      /\| 本月采购额 \|/.test(fixed) &&
      !/\|数值\|\|/.test(fixed) &&
      !/\|数值\|列2\|/.test(fixed)
    const summaryOutside = !/\|[^\n]*\|\n\*\*?趋势小结/.test(fixed)
    const summaryNotInTable = !/<td>\*\*?趋势小结/.test(md.render(fixed))
    return (
      again === fixed &&
      noFake &&
      warnOk &&
      trendOk &&
      monthKpi &&
      summaryOutside &&
      summaryNotInTable
    )
  },
})

cases.push({
  name: 'dashboard-kpi-mash-nmonth-and-year-glued',
  sample: `## 采购仪表盘

| 指标 | 数值 |
|------|------|
| 物料总数 | 75 |
| 供应商数 | 6 |
| 本月采购额 | ¥85,175.86 |
| 本月订单数 | 11笔（完成0笔） |
| 项目 | 内容 |
| 1月 | 75,818 |
| 8 |
| 2月 | 135,087 |
| 8 |
| 3月 | 169,008 |
| 15 |
| 4月 | 226,841 |
| 14 |
| 5月 | 156,796 |
| 16 |
| 6月 | 164,243 |
| 14 |
| 7月 | 85,176 |
| 11 |

**风险要点**

| 序号 | 风险说明 |
| ------ | ------ |
| 1 | 库存 SKU |

📉4月为年度峰值（¥22.7万），5-7月逐步回落。7月环比下降约48%，且尚有11条近效期批次需关注

近效期预警批次 11
MSL预警批次 0 —

##月度采购趋势（2026） 月份 采购额（¥） 订单数
`,
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const noFake =
      !/\|\s*列\s*[12]\s*\|/.test(fixed) && !/\|\s*项目\s*\|\s*内容\s*\|/.test(fixed)
    const noOrphanOc = !/\|\s*8\s*\|\s*\n\|\s*2月/.test(fixed)
    const kpiClean =
      /\| 物料总数 \|/.test(fixed) &&
      /\| 本月采购额 \|/.test(fixed) &&
      !/\|\s*1月\s*\|/.test(fixed.slice(0, fixed.indexOf('月度采购趋势') || fixed.length))
    const trendOk =
      /\| 月份 \|/.test(fixed) &&
      /\| 2026-01 \|/.test(fixed) &&
      /\| 2026-04 \|/.test(fixed) &&
      /¥226,841/.test(fixed) &&
      /\| 2026-01 \|[^|\n]*\| 8 \|/.test(fixed) &&
      !/月度采购趋势[^\n]{0,40}月份[ \t]+采购额/.test(fixed)
    const warnOk = /近效期批次/.test(fixed) && /MSL开封超时/.test(fixed)
    const summaryOut =
      !/\|[^\n]*\|\n\*\*?趋势小结/.test(fixed) &&
      !/<td>\*\*?趋势小结/.test(md.render(fixed))
    return (
      again === fixed &&
      noFake &&
      noOrphanOc &&
      kpiClean &&
      trendOk &&
      warnOk &&
      summaryOut
    )
  },
})

cases.push({
  name: 'risk-emoji-mash + chart-in-risk-cell',
  sample: `**风险要点**
| 序号 | 风险说明 |
| --- | --- |
| 1 | 🔴 Digi-Key无 LDO物料，品类覆盖为零，无法形成双渠道竞争- 🟡 LDO仅 AMS1117一个型号，缺乏多规格 (1.8V/5.0V/可调等) 覆盖- 🟡 华强散新货源品质不稳定 (信用 B)，存在批次一致性风险- 🟢 MSL=1无潮敏风险，无近效期问题，仓储压力低 |
| 2 | MSL 1 - 1 |
| 3 | ![LDO供应商综合对比：立创 vs Digi-Key](https://mdn.alipayobjects.com/example/ldo-chart.png) |

---
后续说明`,
  check: (fixed) => {
    const riskStart = fixed.indexOf('**风险要点**')
    const riskEnd = fixed.search(/\n---\s*\n/)
    const risk = fixed.slice(riskStart, riskEnd > 0 ? riskEnd : undefined)
    const rows = (risk.match(/^\|\s*\d+\s*\|/gm) || []).length
    const chartOutside =
      /!\[[^\]]*\]\(https:\/\/mdn\.alipayobjects\.com\/example\/ldo-chart\.png\)/.test(fixed) &&
      !/^\|[^\n]*!\[[^\]]*\]\(/m.test(fixed)
    const splitOk =
      rows >= 4 &&
      /Digi-Key无 LDO/.test(risk) &&
      /AMS1117/.test(risk) &&
      /华强散新/.test(risk) &&
      /潮敏/.test(risk) &&
      !/^\|\s*\d+\s*\|[^|\n]*🔴[^|\n]*🟡/mu.test(risk)
    const noJunk = !/^\|\s*\d+\s*\|\s*MSL\s*1\s*-\s*1\s*\|/m.test(risk)
    const again = normalizeMarkdown(fixed)
    return chartOutside && splitOk && noJunk && again === fixed
  },
})

cases.push({
  name: 'action-spill + selection-quickcheck-mash',
  sample: `## 七、结论与行动建议

LDO品类当前现状：**立创独大**。

|序号 |事项 |优先级 |建议 |
|---|---|---|---|
|1|Digi-Key LDO品类补录|||

🔴紧急
从 Digi-Key引入至少2~3款 LDO，建立第二高质量渠道 2 华强散新品质管控 🟡高 华强渠道虽便宜21%，禁止用于关键电路 3 LDO多规格扩展 🟡中 当前仅有3.3V一款 4 立创涨价监控 🟢低 立创涨幅持续跟踪 ###选型建议速查 场景 推荐渠道 理由 ------ ---------- ------ **量产主力采购** 立创商城 交期仅2天、全新原装 **极致降本（非关键电路）** 华强电子网 便宜21% **高可靠性 /出口产品** **暂无渠道（紧急补录 Digi-Key）** Digi-Key信用 A **多规格 LDO需求** Digi-Key（补录后）+立创 Digi-Key可补多电压 ---

---

是否需要将此报告下载到本地？回复「下载」即可。
`,
  check: (fixed) => {
    const actionRows = (fixed.match(/^\|\s*\d+\s*\|/gm) || []).length
    const actionOk =
      actionRows >= 4 &&
      /Digi-Key LDO品类补录/.test(fixed) &&
      /华强散新品质管控/.test(fixed) &&
      /LDO多规格扩展/.test(fixed) &&
      /立创涨价监控/.test(fixed) &&
      !/\|\s*1\s*\|[^|\n]+\|\s*\|\s*\|/.test(fixed) &&
      !/建立第二高质量渠道 2 华强/.test(fixed)
    const quickOk =
      /###\s*选型建议速查/.test(fixed) &&
      /\| 场景 \| 推荐渠道 \| 理由 \|/.test(fixed) &&
      /量产主力采购/.test(fixed) &&
      /暂无渠道（紧急补录 Digi-Key）/.test(fixed) &&
      !/选型建议速查[^\n]*场景[ \t]+推荐渠道/.test(fixed)
    const again = normalizeMarkdown(fixed)
    const noBroken =
      !fixed.includes('\uFFFD') &&
      !/�/.test(fixed) &&
      !/\|[^|\n]*[🔴🟡🟢🟠][^|\n]*\|/.test(fixed)
    const priText =
      /\|\s*1\s*\|[^|\n]*\|\s*紧急\s*\|/.test(fixed) &&
      /\|\s*2\s*\|[^|\n]*\|\s*高\s*\|/.test(fixed)
    return actionOk && quickOk && noBroken && priText && again === fixed
  },
})

cases.push({
  name: 'supplier-amount-share-zigzag',
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const hasCanon =
      /###\s*按供应商分布（金额）/.test(fixed) &&
      /\| 供应商 \| 采购金额 \(¥\) \| 占比 \|/.test(fixed) &&
      /\| 板多多（PCB原材料垂直平台） \| 1,892,408\.50 \| 70\.1% \|/.test(fixed) &&
      /\| 阿里巴巴1688工业品 \| 454,517\.32 \| 16\.8% \|/.test(fixed) &&
      /\| 华强电子网 \| 8,428\.42 \| 0\.3% \|/.test(fixed)
    const noFake =
      !/\|\s*项目\s*\|\s*内容\s*\|/.test(fixed) &&
      !/\|\s*70\.1%\s*\|\s*阿里巴巴/.test(fixed)
    return hasCanon && noFake && again === fixed
  },
  sample: `### 按供应商分布（金额）|供应商|
|采购金额（¥）|占比|
|--------|------------|
|项目|内容|
|---|---|
|板多多（PCB原材料垂直平台）|1,892,408.50|
| 70.1% | 阿里巴巴1688工业品 | 454,517.32 |
| 16.8% | 得捷电子 Digi-Key | 192,637.43 |
| 7.1% | 立创商城（嘉立创） | 86,351.78 |
| 3.2% | 贸泽电子 Mouser | 65,049.84 |
| 2.4% | 华强电子网 | 8,428.42 |
|0.3%||

---共 **255笔订单**。
`,
})

cases.push({
  name: 'order-integrity-mashed-table',
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const hasCanon =
      /数据完整性校验/.test(fixed) &&
      /\*\*已收集到的订单数据：\*\*/.test(fixed) &&
      /\| 字段 \| 值 \| 状态 \|/.test(fixed) &&
      /\| 物料名称 \| 电解铜箔\s*18um \| ✅ \|/.test(fixed) &&
      /\| partId \| 37 \| ✅ \|/.test(fixed) &&
      /\| 创建人 \| Louis \| ⚠️ 需要 createdById \|/.test(fixed) &&
      /\| 备注 \| - \| ❓/.test(fixed)
    const noGlue =
      !/\|好的，让我进行数据完整性校验/.test(fixed) &&
      !/❓可选\s*---\s*\*\*Schema/.test(fixed) &&
      /\*\*Schema 校验结果：\*\*/.test(fixed) &&
      /\*\*orderDetail（必填）\*\*/.test(fixed) &&
      !/^- \*\*$/m.test(fixed)
    return hasCanon && noGlue && again === fixed
  },
  sample: `|好的，让我进行数据完整性校验。**已收集到的订单数据：**|字段|值|
|---|---|---|
|**物料名称**|电解铜箔18um|✅|
|**partId**|37|✅|
|**MPN**|ED-18UM|✅（核对用）|
|**供应商**|板多多（supplierId=5）|✅|
|**数量**|10（单位：m²）|✅|
|**单价**|¥55.00|✅|
|**创建人**|Louis|⚠️需要 createdBy ID|
|**预计交货日期**|-|❓可选|
|**备注**|-|❓可选 ---**Schema校验结果：**- **orderDetail（必填）**: ✅ partId=37, quantity=10, unitPrice=55.00均已就绪|

- **orderNumber**: ✅可不传，系统自动生成
请问 **Louis的用户 ID**是多少？`,
})

cases.push({
  name: 'order-candidate-table-peel-ask',
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const tableOk =
      /\| ?电解铜箔18um \|/.test(fixed) &&
      /\| ?反转铜箔 RTF18um \|/.test(fixed) &&
      !/180 \|你需要/.test(fixed) &&
      !/6天 \|你要/.test(fixed)
    const askOk =
      (/你需要哪种铜箔/.test(fixed) || /你要下单的是哪一款/.test(fixed)) &&
      !fixed.split('\n').some((l) => l.trim().startsWith('|') && /你要|你需要哪种/.test(l))
    return tableOk && askOk && again === fixed
  },
  sample: `找到了。板多多（supplierId=5）下有3款铜箔物料：

|名称 | MPN |规格 |单价 (¥) | MOQ |交期 |
|------|-----|------|---------|-----|------|
|电解铜箔18um | ED-18UM |18μm1290mm |55.00 |1 |3天 |
|电解铜箔35um | ED-35UM |35μm1290mm |48.00 |1 |4天 |
|反转铜箔 RTF18um | RTF-18UM |18μm |68.00 |1 |6天 |你要下单的是哪一款？请确认物料名称。
`,
})

cases.push({
  name: 'order-collected-prose-to-table',
  check: (fixed) => {
    const again = normalizeMarkdown(fixed)
    const ok =
      /\| 字段 \| 值 \| 状态 \|/.test(fixed) &&
      /\| partId \| 38 \| ✅ \|/.test(fixed) &&
      (/\| 物料名称 \|/.test(fixed) || /电解铜箔/.test(fixed)) &&
      /\| MPN \| ED-35UM \| ✅ \|/.test(fixed) &&
      /\| 数量 \| 10 m² \| ✅ \|/.test(fixed) &&
      /\| 供应商 \|/.test(fixed) &&
      /\| 预计交货 \| 4\s*天 \| ✅ \|/.test(fixed) &&
      !/2026-06-30/.test(fixed) &&
      !/基于当前日期大约/.test(fixed) &&
      !/好的，让我进行数据完整性校验/.test(fixed)
    return ok && again === fixed
  },
  sample: `好的，我来为 Louis创建电解铜箔的采购订单。先整理已有数据：**已收集的数据：**-物料ID：38（partCode: FOIL-ED35，MPN: ED-35UM，电解铜箔35um）-数量：10 m²-单价：¥48.00/m²-供应商：板多多（supplierId:5）-预计交期：4天（约为2026-06-30，基于当前日期大约2026-06-26）-创建人：Louis数据看起来比较完整，我还需要确认——预计交货日期按4天后的日期来计算。`,
})

cases.push({
  name: 'title_and_summary_out_of_table',
  check: (fixed) => {
    const title = '本月（2026年7月）采购订单明细：共12单'
    const summary = '本月合计：¥85,655.16'
    const issues = findTableHealthIssues(
      `| ${title} | 序号 | 订单ID | 物料名称 | 规格 | 数量 |\n| --- | --- | --- | --- | --- | --- |\n| 1 | 244 | 锂电池 | TP4056 | 397 | ¥0.39 |\n| 12 | 256 | 铜箔 | ED-35 | 10 | 7/22 ${summary}（12单，均无"已取消"标记） |`
    )
    const healthOk =
      issues.includes('title_in_table_header') || issues.includes('summary_in_table_cell')
    const titleOutside =
      fixed.includes(`**${title}**`) &&
      !fixed.split('\n').some((l) => l.startsWith('|') && l.includes(title))
    const noHanghao = !fixed.split('\n').some((l) => l.startsWith('|') && /行号/.test(l))
    const hdr = fixed.split('\n').find((l) => l.startsWith('|') && /序号/.test(l))
    const aligned =
      hdr &&
      /\| 序号 \|/.test(hdr) &&
      /订单ID/.test(hdr) &&
      /单价/.test(hdr) &&
      !/行号/.test(hdr)
    const row1 = fixed.split('\n').find((l) => /^\|/.test(l) && /\|\s*1\s*\|/.test(l) && /244/.test(l))
    const rowOk = row1 && /锂电池/.test(row1) && /¥0\.39/.test(row1)
    return healthOk && titleOutside && noHanghao && aligned && rowOk
  },
  sample: `| 本月（2026年7月）采购订单明细：共12单 | 序号 | 订单ID | 物料名称 | 规格 | 数量 |
| --- | --- | --- | --- | --- | --- |
| 1 | 244 | 锂电池 | TP4056 | 397 | ¥0.39 |
| 12 | 256 | 铜箔 | ED-35 | 10 | 7/22 本月合计：¥85,655.16（12单，均无"已取消"标记） |`,
})

cases.push({
  name: 'date_kept_in_cell_summary_outside',
  check: (fixed) => {
    const pipe = fixed.split('\n').filter((l) => l.startsWith('|'))
    const lastData = pipe[pipe.length - 1] || ''
    const cells = lastData.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
    const dateInCell = cells[cells.length - 1] === '7/22'
    const summaryOutside = fixed
      .split('\n')
      .some((l) => !l.startsWith('|') && /本月合计/.test(l) && !/^\s*7\/22\s+本月合计/.test(l))
    const noDateInSummary = !fixed
      .split('\n')
      .some((l) => !l.startsWith('|') && /^7\/22\s+本月合计/.test(l.trim()))
    return dateInCell && summaryOutside && noDateInSummary
  },
  sample: `| 物料 | 数量 | 金额 | 供应商 | 日期 |
| --- | --- | --- | --- | --- |
| 电解铜箔 | 10 | ¥480.00 | 板多多 | - |

7/22 本月合计：¥85,655.16（12单，均无"已取消"标记）`,
})

cases.push({
  name: 'supplier-summary-peeled-from-money-cell',
  check: (fixed) => {
    const pipe = fixed.split('\n').filter((l) => l.startsWith('|'))
    const lastData = pipe[pipe.length - 1] || ''
    const cells = lastData.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
    const moneyOnly = cells[cells.length - 1] === '¥480.00'
    const proseOut = fixed
      .split('\n')
      .some((l) => !l.startsWith('|') && /按供应商/.test(l))
    const notInPipe = !pipe.some((l) => /按供应商/.test(l))
    return moneyOnly && proseOut && notInPipe
  },
  sample: `| 订单ID | 供应商 | 小计 |
| --- | --- | --- |
| 250 | 华强电子网 | ¥480.00 按供应商 (进行中订单) - 立创商城: 5单 - 板多多: 4单 |`,
})

let failed = 0
for (const c of cases) {
  const fixed = normalizeMarkdown(c.sample)
  const html = md.render(fixed)
  let ok = true
  if (c.check) {
    ok = c.check(fixed, html)
  } else {
    const tr = (html.match(/<tr>/g) || []).length
    const tbody = (html.match(/<tbody>[\s\S]*?<\/tbody>/) || [''])[0]
    const proseInTbody = c.expectOutside ? tbody.includes(c.expectOutside) : false
    const outsideOk = c.expectOutside
      ? fixed.includes(c.expectOutside) &&
        !fixed.split('\n').some((l) => l.startsWith('|') && l.includes(c.expectOutside))
      : true
    ok = html.includes('<table') && tr === c.expectTr && !proseInTbody && outsideOk
  }
  if (!ok) {
    failed++
    console.error('FAIL', c.name)
    console.error(fixed.slice(0, 600))
  } else {
    console.log('PASS', c.name)
  }
}

// 兼容旧 API
if (!fixMarkdownTables('|a|b|\n|---|---|\n|1|2|').includes('|1|2|')) {
  failed++
  console.error('FAIL fixMarkdownTables compat')
}

if (failed) process.exit(1)
console.log('ALL_PASS')
