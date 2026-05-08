<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FileItem, WorkListItem, DirEntry, Breadcrumb, DirectoryListing } from '../types'
import { isFile, isFolder, formatFileSize } from '../types'
import {
  listDirectory, uploadFiles, deleteFile, batchDeleteFiles, renameFile,
  copyFiles, createFolder, deleteFolder, renameFolder,
  getStreamUrl, getPreviewUrl,
} from '../api'
import { usePlayerStore } from '../stores/player'
import { Play, Pause, Image as ImageIcon, FileText, File as FileIcon, MoreHorizontal, Trash2, Edit2, Copy, Upload, Folder, FolderPlus, ChevronRight, Home } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const playerStore = usePlayerStore()

const props = defineProps<{
  workId: number
  allWorks: WorkListItem[]
}>()

const emit = defineEmits<{
  refresh: []
  play: [file: FileItem]
  preview: [file: FileItem]
  audioListUpdate: [audioFiles: FileItem[]]
}>()

// ========== 状态 ==========
const currentPath = ref((route.query.path as string) || '')
const directories = ref<DirectoryListing | null>(null)
const loading = ref(false)
const selectedFileIds = ref<Set<number>>(new Set())
const selectedFolderPaths = ref<Set<string>>(new Set())
const uploading = ref(false)
const uploadProgress = ref('')

const dragCounter = ref(0)
const isDragging = computed(() => dragCounter.value > 0)

// 重命名
const renamingTarget = ref<{ type: 'file' | 'folder'; id?: number; path?: string } | null>(null)
const renameValue = ref('')

// 新建文件夹
const showNewFolderInput = ref(false)
const newFolderName = ref('')

// 复制菜单
const showCopyMenu = ref(false)

// 右键菜单
const contextMenu = ref<{ x: number; y: number; target: DirEntry } | null>(null)

// 音频时长缓存
const audioDurations = ref<Record<number, string>>({})

// ========== 计算属性 ==========
const breadcrumbs = computed(() => directories.value?.breadcrumbs || [{ name: 'ROOT', path: '' }])
const entries = computed(() => directories.value?.entries || [])

const files = computed(() => entries.value.filter(isFile))
const folders = computed(() => entries.value.filter(isFolder))

const otherWorks = computed(() => props.allWorks.filter(w => w.id !== props.workId))

const hasSelection = computed(() => selectedFileIds.value.size > 0 || selectedFolderPaths.value.size > 0)

// ========== 数据加载 ==========
async function loadDirectory() {
  loading.value = true
  try {
    directories.value = await listDirectory(props.workId, currentPath.value || undefined)
  } catch {
    directories.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDirectory()
})

// ========== 音频时长预加载 ==========
function loadAudioDurations() {
  files.value.forEach(file => {
    if (!file.id) return
    if (file.file_type === 'audio' && !audioDurations.value[file.id]) {
      const audio = new Audio(getStreamUrl(file.id))
      audio.addEventListener('loadedmetadata', () => {
        const duration = audio.duration
        if (isFinite(duration)) {
          const m = Math.floor(duration / 60)
          const s = Math.floor(duration % 60)
          audioDurations.value[file.id] = `${m}:${s.toString().padStart(2, '0')}`
        }
      })
    }
  })
}

watch(entries, () => {
  loadAudioDurations()
  // 通知父组件当前文件夹的音频文件列表
  const audioFiles = files.value.filter(f => f.file_type === 'audio')
  emit('audioListUpdate', audioFiles)
})

// ========== 导航 ==========
function navigateTo(path: string) {
  currentPath.value = path
  selectedFileIds.value = new Set()
  selectedFolderPaths.value = new Set()
  showCopyMenu.value = false
  closeContextMenu()
  // 同步 URL query，支持浏览器前进/后退
  const query = { ...route.query, path: path || undefined }
  router.push({ query })
  loadDirectory()
}

// 监听浏览器前进/后退
watch(() => route.query.path, (newPath) => {
  const p = (newPath as string) || ''
  if (p !== currentPath.value) {
    currentPath.value = p
    selectedFileIds.value = new Set()
    selectedFolderPaths.value = new Set()
    showCopyMenu.value = false
    closeContextMenu()
    loadDirectory()
  }
})

// ========== 选择 ==========
function toggleFileSelect(fileId: number) {
  const s = new Set(selectedFileIds.value)
  if (s.has(fileId)) s.delete(fileId)
  else s.add(fileId)
  selectedFileIds.value = s
}

function toggleFolderSelect(folderPath: string) {
  const s = new Set(selectedFolderPaths.value)
  if (s.has(folderPath)) s.delete(folderPath)
  else s.add(folderPath)
  selectedFolderPaths.value = s
}

function handleFolderClick(e: MouseEvent, folderPath: string) {
  if (e.ctrlKey || e.metaKey) {
    toggleFolderSelect(folderPath)
  }
}

function handleFileClick(e: MouseEvent, fileId: number) {
  if (e.ctrlKey || e.metaKey) {
    toggleFileSelect(fileId)
  }
}

// ========== 上传 ==========
async function doUpload(filesToUpload: File[]) {
  if (filesToUpload.length === 0) return
  uploading.value = true
  const total = filesToUpload.length
  try {
    for (let i = 0; i < total; i++) {
      uploadProgress.value = `(${i + 1}/${total})`
      await uploadFiles(props.workId, [filesToUpload[i]], currentPath.value || undefined, (p) => {
        // 分块上传时显示详细进度
        if (p.chunkIndex && p.chunkTotal && p.chunkTotal > 1) {
          uploadProgress.value = `(${i + 1}/${total}) 分块 ${p.chunkIndex}/${p.chunkTotal}`
        }
      })
      await loadDirectory() // 立即刷新列表显示新上传的文件
    }
  } finally {
    uploading.value = false
    uploadProgress.value = ''
    emit('refresh')
  }
}

async function handleUpload(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length) return
  const files = Array.from(input.files)
  input.value = ''
  await doUpload(files)
}

function handleDragEnter(e: DragEvent) {
  if (e.dataTransfer?.types.includes('Files')) {
    dragCounter.value++
  }
}

function handleDragLeave(e: DragEvent) {
  if (dragCounter.value > 0) {
    dragCounter.value--
  }
}

async function handleDrop(e: DragEvent) {
  dragCounter.value = 0
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    await doUpload(Array.from(files))
  }
}

// ========== 文件操作 ==========
async function handleDeleteFile(fileId: number) {
  if (!confirm('确定删除此文件？')) return
  await deleteFile(fileId)
  await loadDirectory()
  emit('refresh')
}

async function handleBatchDelete() {
  const fileCount = selectedFileIds.value.size
  const folderCount = selectedFolderPaths.value.size
  let msg = ''
  if (fileCount > 0 && folderCount > 0) {
    msg = `确定删除选中的 ${fileCount} 个文件和 ${folderCount} 个文件夹？`
  } else if (fileCount > 0) {
    msg = `确定删除选中的 ${fileCount} 个文件？`
  } else {
    msg = `确定删除选中的 ${folderCount} 个文件夹？`
  }
  if (!confirm(msg)) return

  // 先删除文件
  if (fileCount > 0) {
    await batchDeleteFiles(Array.from(selectedFileIds.value))
  }
  // 再删除文件夹
  for (const folderPath of selectedFolderPaths.value) {
    await deleteFolder(props.workId, folderPath)
  }

  selectedFileIds.value = new Set()
  selectedFolderPaths.value = new Set()
  await loadDirectory()
  emit('refresh')
}

function startRenameFile(file: FileItem) {
  renamingTarget.value = { type: 'file', id: file.id }
  renameValue.value = file.filename
}

function startRenameFolder(folderPath: string, folderName: string) {
  renamingTarget.value = { type: 'folder', path: folderPath }
  renameValue.value = folderName
}

async function confirmRename() {
  if (!renameValue.value.trim() || !renamingTarget.value) return
  const target = renamingTarget.value
  try {
    if (target.type === 'file' && target.id) {
      await renameFile(target.id, renameValue.value.trim())
    } else if (target.type === 'folder' && target.path) {
      await renameFolder(props.workId, target.path, renameValue.value.trim())
    }
  } catch {
    // ignore
  }
  renamingTarget.value = null
  await loadDirectory()
  emit('refresh')
}

function cancelRename() {
  renamingTarget.value = null
}

async function handleCopyTo(targetWorkId: number) {
  if (selectedFileIds.value.size === 0) return
  await copyFiles(Array.from(selectedFileIds.value), targetWorkId)
  selectedFileIds.value = new Set()
  showCopyMenu.value = false
  await loadDirectory()
  emit('refresh')
}

// ========== 文件夹操作 ==========
function startNewFolder() {
  showNewFolderInput.value = true
  newFolderName.value = ''
}

async function confirmNewFolder() {
  const name = newFolderName.value.trim()
  if (!name) {
    showNewFolderInput.value = false
    return
  }
  try {
    await createFolder(props.workId, name, currentPath.value || undefined)
  } catch {
    // ignore
  }
  newFolderName.value = ''
  showNewFolderInput.value = false
  await loadDirectory()
  emit('refresh')
}

async function handleDeleteFolder(folderPath: string) {
  if (!confirm('确定删除此文件夹及其所有内容？')) return
  await deleteFolder(props.workId, folderPath)
  await loadDirectory()
  emit('refresh')
}

// ========== 右键菜单 ==========
function handleContextMenu(e: MouseEvent, entry: DirEntry) {
  e.preventDefault()
  contextMenu.value = { x: e.clientX, y: e.clientY, target: entry }
}

function closeContextMenu() {
  contextMenu.value = null
}

function canPlay(file: FileItem) {
  return file.file_type === 'audio' || file.file_type === 'video'
}

function canPreview(file: FileItem) {
  return file.file_type === 'image' || file.file_type === 'text'
}
</script>

<template>
  <div 
    class="bg-white rounded-lg overflow-hidden relative" 
    @click="closeContextMenu"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
  >
    <!-- 拖拽提示层 -->
    <div 
      v-show="isDragging"
      class="absolute inset-0 bg-blue-50/90 z-40 flex flex-col items-center justify-center border-2 border-dashed border-blue-400 m-2 rounded-lg pointer-events-none transition-opacity"
    >
      <Upload class="w-12 h-12 text-blue-500 mb-2 animate-bounce" />
      <p class="text-blue-600 font-medium text-lg">松开鼠标以上传文件</p>
    </div>

    <!-- 工具栏 -->
    <div class="p-4 border-b border-gray-200 bg-white">
      <div class="flex flex-col sm:flex-row gap-3 sm:items-center justify-end">
        <div class="flex flex-wrap items-center gap-2">
          <!-- 新建文件夹 -->
          <button
            class="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 rounded transition-colors"
            @click="startNewFolder"
          >
            <FolderPlus class="w-4 h-4" />
            新建文件夹
          </button>
          <!-- 批量删除 -->
          <button
            v-if="hasSelection"
            class="flex items-center gap-1 px-3 py-1.5 text-sm bg-red-50 text-red-600 hover:bg-red-100 rounded transition-colors"
            @click="handleBatchDelete"
          >
            <Trash2 class="w-4 h-4" />
            批量删除
          </button>
          <!-- 复制到 -->
          <div v-if="selectedFileIds.size > 0 && otherWorks.length > 0" class="relative">
            <button
              class="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 rounded transition-colors"
              @click.stop="showCopyMenu = !showCopyMenu"
            >
              <Copy class="w-4 h-4" />
              复制到...
            </button>
            <div
              v-if="showCopyMenu"
              class="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded shadow-lg z-30 py-1 min-w-[160px] max-h-48 overflow-y-auto"
            >
              <button
                v-for="w in otherWorks"
                :key="w.id"
                class="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 transition-colors truncate"
                @click.stop="handleCopyTo(w.id)"
              >
                {{ w.title || w.rj_code }}
              </button>
            </div>
          </div>
          <!-- 上传按钮 -->
          <label class="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-50 text-blue-600 hover:bg-blue-100 rounded transition-colors" :class="uploading ? 'opacity-75 cursor-wait' : 'cursor-pointer'">
            <Upload class="w-4 h-4" />
            {{ uploading ? `上传中... ${uploadProgress}` : '上传文件' }}
            <input type="file" multiple class="hidden" @change="handleUpload" :disabled="uploading" />
          </label>
        </div>
      </div>
    </div>

    <!-- 面包屑导航 -->
    <div class="flex items-center gap-1 px-4 py-3 border-b border-gray-200 bg-gray-50 overflow-x-auto">
      <button
        v-for="(crumb, index) in breadcrumbs"
        :key="crumb.path"
        class="flex items-center gap-1 text-sm font-medium whitespace-nowrap hover:text-blue-600 transition-colors flex-shrink-0"
        :class="index === breadcrumbs.length - 1 ? 'text-blue-600' : 'text-gray-500'"
        @click="navigateTo(crumb.path)"
      >
        <Home v-if="index === 0" class="w-3.5 h-3.5" />
        <span>{{ crumb.name }}</span>
        <ChevronRight v-if="index < breadcrumbs.length - 1" class="w-3.5 h-3.5 text-gray-300" />
      </button>
    </div>

    <div class="p-4">
      <!-- 新建文件夹输入框 -->
      <div v-if="showNewFolderInput" class="flex items-center gap-2 mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
        <Folder class="w-5 h-5 text-blue-500" />
        <input
          v-model="newFolderName"
          class="flex-1 px-2 py-1 bg-white border border-gray-300 rounded text-sm text-gray-900 focus:outline-none focus:border-blue-500"
          placeholder="文件夹名称"
          @keyup.enter="confirmNewFolder"
          @keyup.escape="showNewFolderInput = false"
          autofocus
        />
        <button class="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors" @click="confirmNewFolder">
          确定
        </button>
        <button class="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors" @click="showNewFolderInput = false">
          取消
        </button>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="entries.length === 0" class="flex flex-col items-center justify-center py-12 text-gray-400">
        <Folder class="w-12 h-12 mb-2 text-gray-300" />
        <p class="text-sm">此文件夹为空</p>
      </div>

      <!-- 条目列表 -->
      <div v-else class="divide-y divide-gray-100">
        <!-- 文件夹 -->
        <div
          v-for="folder in folders"
          :key="folder.path"
          class="flex items-center gap-3 p-3 hover:bg-gray-50 transition-colors group cursor-pointer"
          :class="{ 'bg-blue-50': selectedFolderPaths.has(folder.path) }"
          @click="handleFolderClick($event, folder.path)"
          @dblclick="navigateTo(folder.path)"
          @contextmenu="(e: MouseEvent) => handleContextMenu(e, folder)"
        >
          <div class="w-8 h-8 rounded-lg bg-amber-100 text-amber-600 flex items-center justify-center flex-shrink-0">
            <Folder class="w-4 h-4 fill-amber-200" />
          </div>
          <div class="flex-1 min-w-0">
            <input
              v-if="renamingTarget?.type === 'folder' && renamingTarget.path === folder.path"
              v-model="renameValue"
              class="w-full px-2 py-1 bg-white border border-blue-500 rounded text-sm text-gray-900 focus:outline-none shadow-sm"
              @keyup.enter="confirmRename"
              @keyup.escape="cancelRename"
              @blur="confirmRename"
              @click.stop
              autofocus
            />
            <div v-else class="text-sm text-gray-900 font-medium truncate inline-block max-w-full cursor-pointer hover:text-blue-600" @click="(e) => { if (e.ctrlKey || e.metaKey) return; navigateTo(folder.path) }">
              {{ folder.name }}
            </div>
          </div>
          <!-- 操作按钮 -->
          <div class="flex items-center gap-2 flex-shrink-0 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
            <button
              class="p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded transition-colors"
              title="重命名"
              @click.stop="startRenameFolder(folder.path, folder.name)"
            >
              <Edit2 class="w-4 h-4" />
            </button>
            <button
              class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
              title="删除"
              @click.stop="handleDeleteFolder(folder.path)"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
        </div>

        <!-- 文件 -->
        <div
          v-for="file in files"
          :key="file.id"
          class="flex items-center gap-3 p-3 hover:bg-gray-50 transition-colors group cursor-pointer"
          :class="{ 'bg-blue-50': selectedFileIds.has(file.id) }"
          @click="handleFileClick($event, file.id)"
          @contextmenu="(e: MouseEvent) => handleContextMenu(e, file)"
        >
          <!-- 播放按钮/图标 -->
          <button 
            v-if="canPlay(file)"
            class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm transition-colors"
            :class="playerStore.currentFile?.id === file.id ? 'bg-purple-500 text-white hover:bg-purple-600' : 'bg-blue-500 text-white hover:bg-blue-600'"
            @click.stop="emit('play', file)"
          >
            <Pause v-if="playerStore.currentFile?.id === file.id && playerStore.isPlaying" class="w-4 h-4 fill-current" />
            <Play v-else class="w-4 h-4 fill-current ml-0.5" />
          </button>
          <div v-else-if="file.file_type === 'image'" class="w-8 h-8 rounded flex items-center justify-center flex-shrink-0 overflow-hidden bg-gray-100 border border-gray-200">
            <img v-if="file.id" :src="getPreviewUrl(file.id)" alt="thumbnail" class="w-full h-full object-cover" />
            <ImageIcon v-else class="w-4 h-4 text-gray-500" />
          </div>
          <div v-else class="w-8 h-8 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center flex-shrink-0">
            <FileText v-if="file.file_type === 'text'" class="w-4 h-4" />
            <FileIcon v-else class="w-4 h-4" />
          </div>

          <!-- 文件信息 -->
          <div class="flex-1 min-w-0">
            <input
              v-if="renamingTarget?.type === 'file' && renamingTarget.id === file.id"
              v-model="renameValue"
              class="w-full px-2 py-1 bg-white border border-blue-500 rounded text-sm text-gray-900 focus:outline-none shadow-sm"
              @keyup.enter="confirmRename"
              @keyup.escape="cancelRename"
              @blur="confirmRename"
              @click.stop
              autofocus
            />
            <div v-else>
              <div 
                class="text-sm text-gray-900 font-medium truncate inline-block max-w-full cursor-pointer hover:text-blue-600" 
                @click="(e) => { if (e.ctrlKey || e.metaKey) return; canPlay(file) ? emit('play', file) : canPreview(file) ? emit('preview', file) : null }"
              >
                {{ file.filename }}
              </div>
              <div class="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                <span v-if="file.file_type === 'audio' && audioDurations[file.id]">{{ audioDurations[file.id] }}</span>
                <span v-else>{{ formatFileSize(file.file_size) }}</span>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex items-center gap-2 flex-shrink-0 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
            <button
              class="p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded transition-colors"
              title="重命名"
              @click.stop="startRenameFile(file)"
            >
              <Edit2 class="w-4 h-4" />
            </button>
            <button
              class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
              title="删除"
              @click.stop="handleDeleteFile(file.id)"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 右键菜单 -->
    <div
      v-if="contextMenu"
      class="fixed z-50 bg-white border border-gray-200 rounded shadow-lg py-1 min-w-[140px]"
      :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      @click.stop
    >
      <template v-if="isFile(contextMenu.target)">
        <button v-if="canPlay(contextMenu.target)" class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2" @click="emit('play', contextMenu.target); closeContextMenu()">
          <Play class="w-4 h-4" /> 播放
        </button>
        <button v-if="canPreview(contextMenu.target)" class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2" @click="emit('preview', contextMenu.target); closeContextMenu()">
          <ImageIcon class="w-4 h-4" /> 预览
        </button>
        <button class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2" @click="startRenameFile(contextMenu.target); closeContextMenu()">
          <Edit2 class="w-4 h-4" /> 重命名
        </button>
        <div class="border-t border-gray-100 my-1"></div>
        <button class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2" @click="handleDeleteFile(contextMenu.target.id); closeContextMenu()">
          <Trash2 class="w-4 h-4" /> 删除
        </button>
      </template>
      <template v-else-if="isFolder(contextMenu.target)">
        <button class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2" @click="navigateTo(contextMenu.target.path); closeContextMenu()">
          <Folder class="w-4 h-4" /> 打开
        </button>
        <button class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2" @click="startRenameFolder(contextMenu.target.path, contextMenu.target.name); closeContextMenu()">
          <Edit2 class="w-4 h-4" /> 重命名
        </button>
        <div class="border-t border-gray-100 my-1"></div>
        <button class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2" @click="handleDeleteFolder(contextMenu.target.path); closeContextMenu()">
          <Trash2 class="w-4 h-4" /> 删除
        </button>
      </template>
    </div>
  </div>
</template>
