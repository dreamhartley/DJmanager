<script setup lang="ts">
defineProps<{
  src: string
  filename: string
}>()
</script>

<template>
  <div class="bg-black">
    <video
      :src="src"
      controls
      class="w-full max-h-[70vh]"
      preload="metadata"
      controlsList="nodownload"
    >
      您的浏览器不支持视频播放
    </video>
  </div>
</template>
