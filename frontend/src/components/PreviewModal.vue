<script setup lang="ts">
import { computed } from 'vue'
import type { FileItem } from '../types'
import { getStreamUrl, getPreviewUrl } from '../api'
import VideoPlayer from './VideoPlayer.vue'
import TextPreview from './TextPreview.vue'

const props = defineProps<{
  file: FileItem
  mode: 'play' | 'preview'
}>()

const emit = defineEmits<{
  close: []
}>()

const streamUrl = computed(() => getStreamUrl(props.file.id))
const previewUrl = computed(() => getPreviewUrl(props.file.id))

const componentType = computed(() => {
  if (props.mode === 'play') {
    // 音频由全局播放器处理，这里只处理视频
    return props.file.file_type === 'video' ? 'video' : props.file.file_type
  }
  return props.file.file_type
})
</script>

<template>
  <!-- 纯图片查看器 -->
  <div 
    v-if="componentType === 'image'" 
    class="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 backdrop-blur-sm cursor-zoom-out" 
    @click="emit('close')"
  >
    <img 
      :src="previewUrl" 
      :alt="file.filename" 
      class="max-w-[95vw] max-h-[95vh] object-contain rounded shadow-2xl cursor-default" 
      @click.stop
    />
  </div>

  <!-- 其他类型预览（视频、文本） -->
  <div v-else class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm" @click.self="emit('close')">
    <div class="relative w-full max-w-4xl mx-4 max-h-[90vh] flex flex-col">
      <!-- 关闭按钮 -->
      <button
        class="absolute -top-10 right-0 text-gray-400 hover:text-white transition-colors"
        @click="emit('close')"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <!-- 标题 -->
      <p class="text-sm text-gray-400 mb-2 truncate">{{ file.filename }}</p>

      <!-- 内容区 -->
      <div class="bg-gray-900 rounded-xl overflow-hidden border border-gray-700 flex-1">
        <VideoPlayer v-if="componentType === 'video'" :src="streamUrl" :filename="file.filename" />
        <TextPreview v-else-if="componentType === 'text'" :src="previewUrl" :filename="file.filename" />
        <div v-else class="flex items-center justify-center py-20 text-gray-500">
          不支持预览此文件类型
        </div>
      </div>
    </div>
  </div>
</template>
