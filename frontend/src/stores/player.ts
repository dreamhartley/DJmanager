import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { FileItem } from '../types'
import { getStreamUrl } from '../api'

export const usePlayerStore = defineStore('player', () => {
  // ========== 播放列表状态 ==========
  const playlist = ref<FileItem[]>([])
  const currentIndex = ref(-1)
  const currentWorkId = ref<number | null>(null)
  const coverUrl = ref('')
  const workTitle = ref('')

  // ========== 播放控制状态 ==========
  const isPlaying = ref(false)
  const isExpanded = ref(true)
  const isVisible = ref(false) // 播放器是否可见（至少播放过一次后可见）

  // ========== 进度状态 ==========
  const currentTime = ref(0)
  const duration = ref(0)

  // ========== 音量状态 ==========
  const volume = ref(1)
  const isMuted = ref(false)

  // ========== 计算属性 ==========
  const currentFile = computed(() => {
    if (currentIndex.value >= 0 && currentIndex.value < playlist.value.length) {
      return playlist.value[currentIndex.value]
    }
    return null
  })

  const currentStreamUrl = computed(() => {
    if (currentFile.value) {
      return getStreamUrl(currentFile.value.id)
    }
    return ''
  })

  const hasNext = computed(() => currentIndex.value < playlist.value.length - 1)
  const hasPrev = computed(() => currentIndex.value > 0)

  const progressPercent = computed(() => {
    if (!duration.value) return 0
    return (currentTime.value / duration.value) * 100
  })

  // ========== 方法 ==========

  /**
   * 播放文件，同时设置播放列表
   * 如果 workId 与当前播放列表相同且文件在列表中，则仅切换文件
   * 否则替换整个播放列表
   */
  function playFile(
    file: FileItem,
    audioFiles: FileItem[],
    wId: number,
    cover: string,
    title: string,
  ) {
    if (currentWorkId.value === wId) {
      // 同一作品，检查文件是否在当前播放列表中
      const existingIndex = playlist.value.findIndex(f => f.id === file.id)
      if (existingIndex >= 0) {
        // 文件在播放列表中，切换到该文件
        if (currentIndex.value === existingIndex) {
          // 同一文件，切换播放/暂停
          isPlaying.value = !isPlaying.value
          return
        }
        currentIndex.value = existingIndex
        isPlaying.value = true
        isVisible.value = true
        isExpanded.value = true
        return
      }
      // 文件不在列表中（可能目录变了），更新播放列表
    }

    // 不同作品或新播放列表
    playlist.value = [...audioFiles]
    currentWorkId.value = wId
    coverUrl.value = cover
    workTitle.value = title

    const idx = audioFiles.findIndex(f => f.id === file.id)
    currentIndex.value = idx >= 0 ? idx : 0

    isPlaying.value = true
    isVisible.value = true
    isExpanded.value = true
  }

  function playNext() {
    if (hasNext.value) {
      currentIndex.value++
      isPlaying.value = true
    }
  }

  function playPrev() {
    if (hasPrev.value) {
      currentIndex.value--
      isPlaying.value = true
    }
  }

  function togglePlay() {
    isPlaying.value = !isPlaying.value
  }

  function toggleExpand() {
    isExpanded.value = !isExpanded.value
  }

  function setCurrentTime(time: number) {
    currentTime.value = time
  }

  function setDuration(dur: number) {
    duration.value = dur
  }

  function setVolume(vol: number) {
    volume.value = vol
    if (vol > 0) isMuted.value = false
  }

  function toggleMute() {
    isMuted.value = !isMuted.value
  }

  function onTrackEnded() {
    if (hasNext.value) {
      playNext()
    } else {
      isPlaying.value = false
    }
  }

  function playAt(index: number) {
    if (index >= 0 && index < playlist.value.length) {
      currentIndex.value = index
      isPlaying.value = true
    }
  }

  return {
    // 状态
    playlist,
    currentIndex,
    currentWorkId,
    coverUrl,
    workTitle,
    isPlaying,
    isExpanded,
    isVisible,
    currentTime,
    duration,
    volume,
    isMuted,
    // 计算属性
    currentFile,
    currentStreamUrl,
    hasNext,
    hasPrev,
    progressPercent,
    // 方法
    playFile,
    playNext,
    playPrev,
    togglePlay,
    toggleExpand,
    setCurrentTime,
    setDuration,
    setVolume,
    toggleMute,
    onTrackEnded,
    playAt,
  }
})
