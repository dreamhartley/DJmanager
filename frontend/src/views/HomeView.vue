<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useWorksStore } from '../stores/works'
import { addWork, deleteWork } from '../api'
import CoverCard from '../components/CoverCard.vue'
import AddWorkDialog from '../components/AddWorkDialog.vue'
import { Plus, Flame, Trash2, AlertTriangle } from 'lucide-vue-next'

const store = useWorksStore()
const showAddDialog = ref(false)
const adding = ref(false)
const error = ref('')

// 删除确认模态框状态
const showDeleteModal = ref(false)
const deleteTargetId = ref<number | null>(null)
const deleteTargetRjCode = ref('')
const deleteConfirmInput = ref('')
const deleting = ref(false)
const deleteError = ref('')
const deleteInputRef = ref<HTMLInputElement | null>(null)

const isDeleteConfirmMatch = computed(() => {
  return deleteConfirmInput.value.trim().toUpperCase() === deleteTargetRjCode.value.toUpperCase()
})

onMounted(() => {
  store.fetchWorks()
})

async function handleAddWork(rjCode: string) {
  adding.value = true
  error.value = ''
  try {
    await addWork(rjCode)
    showAddDialog.value = false
    await store.fetchWorks()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '添加失败'
    error.value = msg
  } finally {
    adding.value = false
  }
}

function handleDeleteWork(id: number) {
  const work = store.works.find(w => w.id === id)
  if (!work) return
  deleteTargetId.value = id
  deleteTargetRjCode.value = work.rj_code
  deleteConfirmInput.value = ''
  deleteError.value = ''
  deleting.value = false
  showDeleteModal.value = true
  nextTick(() => {
    deleteInputRef.value?.focus()
  })
}

function closeDeleteModal() {
  showDeleteModal.value = false
  deleteTargetId.value = null
  deleteTargetRjCode.value = ''
  deleteConfirmInput.value = ''
  deleteError.value = ''
}

async function confirmDelete() {
  if (!isDeleteConfirmMatch.value || deleteTargetId.value === null) return
  deleting.value = true
  deleteError.value = ''
  try {
    await deleteWork(deleteTargetId.value)
    closeDeleteModal()
    await store.fetchWorks()
  } catch (e: any) {
    deleteError.value = e?.response?.data?.detail || '删除失败'
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="max-w-[1600px] mx-auto">
    <!-- 顶部操作栏 -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
      <div class="flex items-center gap-2">
        <h1 class="text-xl font-medium text-gray-800 flex items-center gap-2">
          <Flame class="w-5 h-5 text-orange-500" />
          所有作品
        </h1>
        <span class="text-sm text-gray-500">({{ store.works.length }})</span>
      </div>
      <button
        class="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors text-sm font-medium shadow-sm"
        @click="showAddDialog = true"
      >
        <Plus class="w-4 h-4" />
        添加作品
      </button>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex justify-between items-center">
      <span>{{ error }}</span>
      <button class="text-red-400 hover:text-red-600" @click="error = ''">关闭</button>
    </div>

    <!-- 加载状态 -->
    <div v-if="store.loading" class="flex items-center justify-center py-20">
      <div class="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full"></div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="store.works.length === 0" class="flex flex-col items-center justify-center py-20 text-gray-400">
      <svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
          d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
      <p class="text-lg text-gray-600">暂无作品</p>
      <p class="text-sm mt-1">点击"添加作品"输入 DLsite RJ 编号开始</p>
    </div>

    <!-- 封面网格 -->
    <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 md:gap-6">
      <CoverCard
        v-for="work in store.works"
        :key="work.id"
        :work="work"
        @delete="handleDeleteWork"
      />
    </div>

    <!-- 添加对话框 -->
    <AddWorkDialog
      v-if="showAddDialog"
      @submit="handleAddWork"
      @close="showAddDialog = false; error = ''"
    />

    <!-- 删除确认模态框 -->
    <Teleport to="body">
      <Transition name="delete-modal">
        <div
          v-if="showDeleteModal"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          @click.self="closeDeleteModal"
        >
          <div class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md mx-4 shadow-2xl">
            <div class="p-6">
              <!-- 警告图标与标题 -->
              <div class="flex items-center gap-3 mb-4">
                <div class="flex-shrink-0 w-10 h-10 rounded-full bg-red-500/15 flex items-center justify-center">
                  <AlertTriangle class="w-5 h-5 text-red-400" />
                </div>
                <h2 class="text-lg font-semibold text-gray-100">确认删除作品</h2>
              </div>

              <!-- 提示信息 -->
              <div class="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                <p class="text-sm text-gray-300">
                  即将删除作品 <span class="font-mono font-bold text-red-400">{{ deleteTargetRjCode }}</span> 及其所有文件，此操作<span class="text-red-400 font-semibold">不可撤销</span>。
                </p>
              </div>

              <!-- 输入框 -->
              <div class="space-y-2">
                <label class="block text-sm text-gray-400">
                  请输入 <span class="font-mono font-bold text-gray-200">{{ deleteTargetRjCode }}</span> 以确认删除
                </label>
                <input
                  ref="deleteInputRef"
                  v-model="deleteConfirmInput"
                  type="text"
                  :placeholder="deleteTargetRjCode"
                  class="w-full px-3 py-2 bg-gray-800 border rounded-lg text-gray-100 placeholder-gray-600 focus:outline-none transition-colors"
                  :class="[
                    deleteConfirmInput.trim() && !isDeleteConfirmMatch
                      ? 'border-red-500/50 focus:border-red-500 focus:ring-1 focus:ring-red-500'
                      : isDeleteConfirmMatch
                        ? 'border-green-500/50 focus:border-green-500 focus:ring-1 focus:ring-green-500'
                        : 'border-gray-700 focus:border-gray-500 focus:ring-1 focus:ring-gray-500'
                  ]"
                  @keyup.enter="confirmDelete"
                />
                <p v-if="deleteError" class="text-red-400 text-xs mt-1">{{ deleteError }}</p>
              </div>
            </div>

            <!-- 底部按钮 -->
            <div class="flex justify-end gap-3 px-6 pb-6">
              <button
                class="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
                @click="closeDeleteModal"
              >
                取消
              </button>
              <button
                class="flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-all duration-200"
                :class="[
                  isDeleteConfirmMatch && !deleting
                    ? 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/20'
                    : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                ]"
                :disabled="!isDeleteConfirmMatch || deleting"
                @click="confirmDelete"
              >
                <Trash2 class="w-4 h-4" />
                {{ deleting ? '删除中...' : '确认删除' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.delete-modal-enter-active,
.delete-modal-leave-active {
  transition: opacity 0.2s ease;
}
.delete-modal-enter-active > div,
.delete-modal-leave-active > div {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.delete-modal-enter-from,
.delete-modal-leave-to {
  opacity: 0;
}
.delete-modal-enter-from > div {
  transform: scale(0.95);
  opacity: 0;
}
.delete-modal-leave-to > div {
  transform: scale(0.95);
  opacity: 0;
}
</style>
