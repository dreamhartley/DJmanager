<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useWorksStore } from '../stores/works'
import { addWork, deleteWork } from '../api'
import CoverCard from '../components/CoverCard.vue'
import AddWorkDialog from '../components/AddWorkDialog.vue'
import { Plus, Flame, Sparkles } from 'lucide-vue-next'

const store = useWorksStore()
const showAddDialog = ref(false)
const adding = ref(false)
const error = ref('')

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

async function handleDeleteWork(id: number) {
  if (!confirm('确定要删除此作品及其所有文件吗？此操作不可撤销。')) return
  try {
    await deleteWork(id)
    await store.fetchWorks()
  } catch (e: any) {
    alert(e?.response?.data?.detail || '删除失败')
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
  </div>
</template>
