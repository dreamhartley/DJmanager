<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  src: string
  filename: string
}>()

const zoom = ref(1)

function zoomIn() {
  zoom.value = Math.min(zoom.value + 0.25, 3)
}

function zoomOut() {
  zoom.value = Math.max(zoom.value - 0.25, 0.25)
}

function resetZoom() {
  zoom.value = 1
}
</script>

<template>
  <div class="relative flex flex-col items-center bg-gray-950">
    <!-- 缩放控制 -->
    <div class="absolute top-2 right-2 z-10 flex items-center gap-1">
      <button class="px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition-colors" @click="zoomOut">−</button>
      <span class="text-xs text-gray-400 w-12 text-center">{{ Math.round(zoom * 100) }}%</span>
      <button class="px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition-colors" @click="zoomIn">+</button>
      <button class="px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition-colors" @click="resetZoom">重置</button>
    </div>

    <div class="overflow-auto max-h-[75vh] w-full flex items-center justify-center p-4">
      <img
        :src="src"
        :alt="filename"
        :style="{ transform: `scale(${zoom})`, transition: 'transform 0.2s' }"
        class="max-w-full object-contain"
      />
    </div>
  </div>
</template>
