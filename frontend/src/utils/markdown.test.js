/**
 * markdown.js 工具单测（node 原生 assert，无框架依赖）。
 * 运行：npm run test:md
 * 历史：旧 markdownTables.test.js 随采购表格重整套一并删除，本文件补测
 * markdown.js 现存的通用能力（图片 host 识别 / 裸链提取 / normalize passthrough）。
 */
import assert from 'node:assert/strict'
import { isKnownImageHost, findKnownImageUrls, normalizeMarkdown } from './markdown.js'

// isKnownImageHost
assert.equal(isKnownImageHost('https://img.shields.io/badge/x-y'), true, 'shields.io 应识别为图床')
assert.equal(isKnownImageHost('https://raw.githubusercontent.com/a/b/main/f.png'), true, 'GitHub raw 应识别')
assert.equal(isKnownImageHost('https://evil.example.com/payload.png'), false, '未知 host 不应识别')
assert.equal(isKnownImageHost(''), false, '空串应返回 false')
assert.equal(isKnownImageHost(null), false, 'null 应返回 false')

// findKnownImageUrls
const text = [
  '看这张图 https://img.shields.io/badge/test-pass.png 以及',
  'https://cdn.pixabay.com/photo/2020/4/1/cat.jpg。',
  '还有非图床链接 https://example.com/page 和 https://do-i-exist.net/mystery.webp',
].join('\n')
const urls = findKnownImageUrls(text)
assert.ok(urls.includes('https://img.shields.io/badge/test-pass.png'), '应提取图床图片')
assert.ok(urls.includes('https://cdn.pixabay.com/photo/2020/4/1/cat.jpg'), '应按扩展名提取并去掉尾部标点')
assert.ok(!urls.includes('https://example.com/page'), '非图片链接不应提取')
assert.deepEqual(findKnownImageUrls(''), [], '空文本返回空数组')

// normalizeMarkdown passthrough
assert.equal(normalizeMarkdown('# hi\n\nbody'), '# hi\n\nbody', 'normalize 应原样透传')
assert.equal(normalizeMarkdown(null), '', 'null 应返回空串')

console.log('markdown.js 单测全部通过 (11 assertions)')
