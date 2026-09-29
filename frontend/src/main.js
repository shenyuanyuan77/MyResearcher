/**
 * Vue 应用入口文件
 *
 * 创建并挂载 Vue 应用
 */

import { createApp } from 'vue'
import App from './App.vue'
import './styles/main.css'
import { applyTheme } from './theme.js'

// 应用主题（index.html 内联脚本已做首帧解析，这里补齐系统切换监听）
applyTheme()

// 创建 Vue 应用实例
const app = createApp(App)

// 挂载到 #app 元素
app.mount('#app')
