<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { usePlayerStore } from '../stores/player'
import { getStreamUrl } from '../api'
import { X, Play, Pause, Music } from 'lucide-vue-next'

const props = defineProps<{
  mini?: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const store = usePlayerStore()

// 音频时长缓存
const durations = ref<Record<number, string>>({})

function formatDuration(seconds: number): string {
  if (!isFinite(seconds)) return ''
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// 预加载时长
function loadDurations() {
  store.playlist.forEach(file => {
    if (!durations.value[file.id]) {
      const audio = new Audio(getStreamUrl(file.id))
      audio.addEventListener('loadedmetadata', () => {
        if (isFinite(audio.duration)) {
          durations.value[file.id] = formatDuration(audio.duration)
        }
      })
    }
  })
}

watch(() => store.playlist, () => {
  loadDurations()
}, { immediate: true })

function handleClickTrack(index: number) {
  if (store.currentIndex === index) {
    store.togglePlay()
  } else {
    store.playAt(index)
  }
}
</script>

<template>
  <div class="playlist-panel" :class="{ 'playlist-mini': mini }">
    <div class="playlist-header">
      <div class="playlist-title">
        <Music class="w-4 h-4" />
        <span>播放列表</span>
        <span class="playlist-count">{{ store.playlist.length }}</span>
      </div>
      <button class="playlist-close" @click="emit('close')">
        <X class="w-4 h-4" />
      </button>
    </div>

    <div class="playlist-items">
      <div
        v-for="(file, index) in store.playlist"
        :key="file.id"
        class="playlist-item"
        :class="{ active: index === store.currentIndex }"
        @click="handleClickTrack(index)"
      >
        <div class="item-icon">
          <template v-if="index === store.currentIndex">
            <Pause v-if="store.isPlaying" class="w-3.5 h-3.5" />
            <Play v-else class="w-3.5 h-3.5" />
          </template>
          <Play v-else class="w-3.5 h-3.5 item-play-icon" />
        </div>
        <div class="item-info">
          <div class="item-name">{{ file.filename }}</div>
        </div>
        <div class="item-duration">{{ durations[file.id] || '' }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.playlist-panel {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  max-height: 320px;
  background: linear-gradient(145deg, #1e1e2e, #252540);
  border-radius: 12px 12px 0 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.3);
  animation: playlistSlideUp 0.2s ease-out;
}

.playlist-mini {
  position: fixed;
  bottom: 56px;
  left: 0;
  right: 0;
  border-radius: 0;
  max-height: 50vh;
}

@keyframes playlistSlideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.playlist-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.playlist-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.playlist-count {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 8px;
  border-radius: 10px;
}

.playlist-close {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}
.playlist-close:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.playlist-items {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.playlist-items::-webkit-scrollbar {
  width: 4px;
}
.playlist-items::-webkit-scrollbar-track {
  background: transparent;
}
.playlist-items::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.playlist-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.15s;
}
.playlist-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.playlist-item.active {
  background: rgba(139, 92, 246, 0.12);
}

.item-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.4);
}
.playlist-item.active .item-icon {
  color: #8b5cf6;
}
.item-play-icon {
  opacity: 0;
}
.playlist-item:hover .item-play-icon {
  opacity: 1;
}

.item-info {
  flex: 1;
  min-width: 0;
}
.item-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.playlist-item.active .item-name {
  color: #8b5cf6;
  font-weight: 500;
}

.item-duration {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
}
</style>
