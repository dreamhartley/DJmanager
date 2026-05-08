<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  submit: [rjCode: string]
  close: []
}>()

const rjCode = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  const code = rjCode.value.trim()
  if (!code) {
    error.value = '请输入 RJ 编号'
    return
  }
  error.value = ''
  loading.value = true
  emit('submit', code)
}

function handleClose() {
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" @click.self="handleClose">
    <div class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md mx-4 shadow-2xl">
      <div class="p-6">
        <h2 class="text-lg font-semibold text-gray-100 mb-4">添加作品</h2>

        <div class="space-y-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1.5">DLsite RJ 编号</label>
            <input
              v-model="rjCode"
              type="text"
              placeholder="例如：RJ01553954"
              class="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
              @keyup.enter="handleSubmit"
              autofocus
            />
            <p v-if="error" class="text-red-400 text-xs mt-1">{{ error }}</p>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-3 px-6 pb-6">
        <button
          class="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
          @click="handleClose"
        >
          取消
        </button>
        <button
          class="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50"
          :disabled="loading"
          @click="handleSubmit"
        >
          {{ loading ? '获取中...' : '添加' }}
        </button>
      </div>
    </div>
  </div>
</template>
