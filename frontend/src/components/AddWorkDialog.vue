<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  loading?: boolean
  error?: string
}>()

const emit = defineEmits<{
  submit: [rjCode: string]
  close: []
  clearError: []
}>()

const rjCode = ref('')
const validationError = ref('')

async function handleSubmit() {
  const code = rjCode.value.trim()
  if (!code) {
    validationError.value = '请输入 RJ 编号'
    return
  }
  validationError.value = ''
  emit('submit', code)
}

function handleClose() {
  emit('close')
}

function handleInput() {
  validationError.value = ''
  emit('clearError')
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-md" @click.self="handleClose">
    <div class="bg-slate-900/75 backdrop-blur-xl border border-white/10 rounded-2xl w-full max-w-md mx-4 shadow-[0_8px_32px_0_rgba(0,0,0,0.5)] ring-1 ring-white/5">
      <div class="p-6">
        <h2 class="text-lg font-semibold text-gray-100 mb-4">添加作品</h2>

        <div class="space-y-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1.5">DLsite RJ 编号</label>
            <input
              v-model="rjCode"
              type="text"
              placeholder="例如：RJ01553954"
              class="w-full px-3 py-2 bg-slate-950/50 border border-slate-700/50 focus:border-primary-500 rounded-lg text-gray-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 transition-all"
              @keyup.enter="handleSubmit"
              @input="handleInput"
              autofocus
            />
            <p v-if="validationError || error" class="text-red-400 text-sm mt-2 flex items-center gap-1.5">
              <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{{ validationError || error }}</span>
            </p>
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
          class="px-4 py-2 text-sm bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-500 hover:to-primary-400 text-white font-medium rounded-lg shadow-lg shadow-primary-500/20 hover:shadow-primary-500/30 transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none"
          :disabled="loading"
          @click="handleSubmit"
        >
          {{ loading ? '获取中...' : '添加' }}
        </button>
      </div>
    </div>
  </div>
</template>

