<script setup lang="ts">
import { computed } from 'vue'
import { RouterView } from 'vue-router'
import { Menu } from 'lucide-vue-next'
import GlobalAudioPlayer from './components/GlobalAudioPlayer.vue'
import { usePlayerStore } from './stores/player'

const playerStore = usePlayerStore()

// 当迷你播放器显示时，给外层容器添加底部间距，使主内容区的高度缩小
const mainPaddingBottom = computed(() => {
  if (playerStore.isVisible && !playerStore.isExpanded) {
    return 'calc(52px + env(safe-area-inset-bottom))'
  }
  return undefined
})
</script>

<template>
  <div class="h-dvh overflow-hidden bg-gray-100 flex flex-col" :style="{ paddingBottom: mainPaddingBottom }">
    <!-- 顶部导航栏 -->
    <header class="h-14 bg-blue-500 text-white flex items-center px-4 flex-shrink-0 z-40 shadow-sm">
      <div class="flex items-center gap-4">
        <button class="p-1 hover:bg-blue-600 rounded">
          <Menu class="w-6 h-6" />
        </button>
        <router-link to="/" class="text-xl font-medium hover:text-blue-100 transition-colors cursor-pointer">
          DJmanager
        </router-link>
      </div>
    </header>

    <!-- 路由视图 -->
    <main class="flex-1 p-4 md:p-6 overflow-y-auto overflow-x-hidden relative">
      <RouterView />
    </main>
  </div>

  <!-- 全局音频播放器 -->
  <GlobalAudioPlayer />
</template>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  overflow: hidden; /* 确保整个网页不出现滚动条 */
}
</style>
