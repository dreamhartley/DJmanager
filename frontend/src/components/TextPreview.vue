<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const props = defineProps<{
  src: string
  filename: string
}>()

const content = ref('')
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await axios.get(props.src)
    content.value = data.content || data
  } catch (e: any) {
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="flex flex-col h-full max-h-[75vh]">
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full"></div>
    </div>
    <div v-else-if="error" class="flex items-center justify-center py-20 text-red-400 text-sm">
      {{ error }}
    </div>
    <pre v-else class="flex-1 overflow-auto p-4 text-sm text-gray-300 font-mono leading-relaxed whitespace-pre-wrap break-all">{{ content }}</pre>
  </div>
</template>
