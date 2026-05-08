<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getWork, listWorks } from '../api'
import { useWorksStore } from '../stores/works'
import { usePlayerStore } from '../stores/player'
import type { Work, FileItem, WorkListItem } from '../types'
import { getCoverUrl } from '../types'
import FileManager from '../components/FileManager.vue'
import PreviewModal from '../components/PreviewModal.vue'
import { 
  ChevronLeft, ExternalLink
} from 'lucide-vue-next'

defineOptions({ inheritAttrs: false })

const route = useRoute()
const router = useRouter()
const store = useWorksStore()
const playerStore = usePlayerStore()

const rjCode = computed(() => route.params.rjCode as string)
const work = ref<Work | null>(null)
const allWorks = ref<WorkListItem[]>([])
const loading = ref(true)
const previewingFile = ref<FileItem | null>(null)
const fileManagerKey = ref(0)

// 当前文件夹中的音频文件列表（由 FileManager 提供）
const currentAudioFiles = ref<FileItem[]>([])

onMounted(async () => {
  await loadData()
})

async function loadData() {
  loading.value = true
  try {
    const [w, aw] = await Promise.all([
      getWork(rjCode.value),
      listWorks(),
    ])
    work.value = w
    allWorks.value = aw
  } catch {
    router.push('/')
  } finally {
    loading.value = false
  }
}

const coverUrl = computed(() => getCoverUrl(work.value?.cover_path || ''))

function handlePlay(file: FileItem) {
  if (!work.value) return
  const cover = getCoverUrl(work.value.cover_path || '')
  const title = work.value.title || work.value.rj_code
  playerStore.playFile(file, currentAudioFiles.value, work.value.id, cover, title)
}

function handleAudioListUpdate(audioFiles: FileItem[]) {
  currentAudioFiles.value = audioFiles
}

function handlePreview(file: FileItem) {
  previewingFile.value = file
}

async function handleRefresh() {
  // 静默刷新，不触发 loading 状态（避免销毁 FileManager）
  try {
    const [w, aw] = await Promise.all([
      getWork(rjCode.value),
      listWorks(),
    ])
    work.value = w
    allWorks.value = aw
  } catch {
    // 静默忽略刷新失败
  }
}
</script>

<template>
  <div v-if="loading" class="flex items-center justify-center py-20">
    <div class="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full"></div>
  </div>

  <template v-else-if="work">
    <div class="max-w-[1600px] mx-auto bg-white min-h-screen">

      <div class="p-4 md:p-6">
        <!-- 作品信息区 -->
        <div class="flex flex-col md:flex-row gap-6 mb-8">
          <!-- 左侧封面 -->
          <div class="flex-shrink-0 w-full md:w-[400px]">
            <div class="relative rounded-lg overflow-hidden shadow-md bg-gray-100 aspect-[4/3]">
              <div class="absolute top-0 left-0 bg-black/60 text-white text-xs px-2 py-1 rounded-br-lg z-10">
                {{ work.rj_code }}
              </div>
              <img
                v-if="coverUrl"
                :src="coverUrl"
                :alt="work.title"
                class="w-full h-full object-cover"
              />
              <div v-else class="w-full h-full flex items-center justify-center text-gray-400">
                <svg class="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <div class="absolute bottom-0 right-0 bg-black/60 text-white text-xs px-2 py-1 rounded-tl-lg z-10">
                {{ work.release_date }}
              </div>
            </div>
          </div>

          <!-- 右侧详细信息 -->
          <div class="flex-1 min-w-0 flex flex-col">
            <h1 class="text-2xl font-bold text-gray-900 mb-2 leading-tight">{{ work.title }}</h1>
            <p class="text-sm text-gray-500 mb-4 hover:text-blue-600 cursor-pointer">{{ work.circle }}</p>

            <!-- 链接与分级 -->
            <div class="flex items-center gap-4 text-sm text-gray-600 mb-6 flex-wrap">
              <a :href="`https://www.dlsite.com/maniax/work/=/product_id/${work.rj_code}.html`" target="_blank" class="flex items-center gap-1 text-blue-500 hover:underline">
                <ExternalLink class="w-4 h-4" />
                DLsite
              </a>
              <span class="text-xs border border-orange-300 text-orange-500 px-1 rounded">
                {{ work.age_category === 1 ? '全年龄' : work.age_category === 2 ? 'R-15' : work.age_category === 3 ? 'R-18' : '未知' }}
              </span>
            </div>

            <!-- 标签区 -->
            <div class="flex flex-wrap gap-2 mb-4">
              <span
                v-for="g in work.genres"
                :key="g"
                class="px-3 py-1 text-xs bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 cursor-pointer"
              >
                {{ g }}
              </span>
            </div>

            <!-- 声优区 -->
            <div class="flex flex-wrap gap-2 mb-4">
              <span
                v-for="va in work.voice_actors"
                :key="va"
                class="px-3 py-1 text-xs bg-teal-600 text-white rounded hover:bg-teal-700 cursor-pointer"
              >
                {{ va }}
              </span>
            </div>

            <!-- 简介区 -->
            <div v-if="work.description" class="mt-4 bg-gray-50 p-4 rounded-lg border border-gray-100 flex-1">
              <h3 class="text-sm font-medium text-gray-700 mb-2">作品简介</h3>
              <div class="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto" v-html="work.description"></div>
            </div>
          </div>
        </div>

        <!-- 文件管理区 -->
        <div class="mt-8 border border-gray-200 rounded-lg bg-white shadow-sm">
          <FileManager
            :key="fileManagerKey"
            :work-id="work.id"
            :all-works="allWorks"
            @refresh="handleRefresh"
            @play="handlePlay"
            @preview="handlePreview"
            @audio-list-update="handleAudioListUpdate"
          />
        </div>
      </div>
    </div>

    <!-- 预览（仅图片/文本） -->
    <Teleport to="body">
      <PreviewModal
        v-if="previewingFile"
        :file="previewingFile"
        mode="preview"
        @close="previewingFile = null"
      />
    </Teleport>
  </template>
</template>
