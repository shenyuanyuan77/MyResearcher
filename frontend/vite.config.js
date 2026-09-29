import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // GitHub Pages 项目站部署在 /MyResearcher/ 子路径，资源用相对引用
  base: './',
  plugins: [vue()],
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: true,
    rollupOptions: {
      output: {
        // 代码分割：重库单独分包，避免主 bundle 过大（曾达 1.17MB 触发告警）
        manualChunks: {
          vue: ['vue'],
          markdown: ['markdown-it', 'highlight.js'],
          mermaid: ['mermaid'],
        },
      },
    },
  },
})
