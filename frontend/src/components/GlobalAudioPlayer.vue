<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { usePlayerStore } from '../stores/player'
import { getStreamUrl } from '../api'
import {
  Play, Pause, SkipBack, SkipForward,
  Volume2, VolumeX, Volume1,
  RotateCcw, RotateCw,
  List, Music, X,
} from 'lucide-vue-next'

const store = usePlayerStore()
const audioRef = ref<HTMLAudioElement | null>(null)
const showPlaylist = ref(false)

// 播放列表时长缓存
const durations = ref<Record<number, string>>({})

function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ========== 播放列表时长 ==========
function loadDurations() {
  store.playlist.forEach(file => {
    if (!durations.value[file.id]) {
      const audio = new Audio(getStreamUrl(file.id))
      audio.addEventListener('loadedmetadata', () => {
        if (isFinite(audio.duration)) {
          durations.value[file.id] = formatTime(audio.duration)
        }
      })
    }
  })
}
watch(() => store.playlist, () => { loadDurations() }, { immediate: true })

function handleClickTrack(index: number) {
  if (store.currentIndex === index) {
    store.togglePlay()
  } else {
    store.playAt(index)
  }
}

// ========== Audio 元素事件 ==========
function onTimeUpdate() {
  if (audioRef.value) store.setCurrentTime(audioRef.value.currentTime)
}
function onLoadedMetadata() {
  if (audioRef.value) store.setDuration(audioRef.value.duration)
}
function onEnded() { store.onTrackEnded() }

// ========== 播放控制 ==========
function seekTo(e: MouseEvent) {
  if (!audioRef.value || !store.duration) return
  const target = e.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const percent = (e.clientX - rect.left) / rect.width
  const newTime = percent * store.duration
  audioRef.value.currentTime = newTime
  store.setCurrentTime(newTime)
}

function seekMini(e: MouseEvent) { seekTo(e) }

function skipBack5() {
  if (!audioRef.value) return
  const t = Math.max(0, audioRef.value.currentTime - 5)
  audioRef.value.currentTime = t
  store.setCurrentTime(t)
}
function skipForward30() {
  if (!audioRef.value) return
  const t = Math.min(store.duration, audioRef.value.currentTime + 30)
  audioRef.value.currentTime = t
  store.setCurrentTime(t)
}

function onVolumeChange(e: Event) {
  const vol = Number((e.target as HTMLInputElement).value)
  store.setVolume(vol)
  if (audioRef.value) { audioRef.value.volume = vol; audioRef.value.muted = false }
}
function handleToggleMute() {
  store.toggleMute()
  if (audioRef.value) audioRef.value.muted = store.isMuted
}

// ========== 监听 store ==========
watch(() => store.isPlaying, (p) => {
  if (!audioRef.value) return
  p ? audioRef.value.play().catch(() => {}) : audioRef.value.pause()
})
watch(() => store.currentStreamUrl, (url) => {
  if (!audioRef.value || !url) return
  store.setCurrentTime(0); store.setDuration(0)
  audioRef.value.src = url; audioRef.value.load()
  if (store.isPlaying) nextTick(() => { audioRef.value?.play().catch(() => {}) })
})
watch(() => store.volume, (v) => { if (audioRef.value) audioRef.value.volume = v })
watch(() => store.isMuted, (m) => { if (audioRef.value) audioRef.value.muted = m })

onMounted(() => {
  if (audioRef.value) {
    audioRef.value.volume = store.volume
    // 组件首次挂载时，如果 store 已有播放状态，手动触发播放
    if (store.currentStreamUrl && store.isPlaying) {
      audioRef.value.src = store.currentStreamUrl
      audioRef.value.load()
      nextTick(() => {
        audioRef.value?.play().catch(() => {})
      })
    }
  }
})

function togglePlaylist() { showPlaylist.value = !showPlaylist.value }

function getVolumeIcon() {
  if (store.isMuted || store.volume === 0) return VolumeX
  if (store.volume < 0.5) return Volume1
  return Volume2
}
</script>

<template>
  <div v-show="store.isVisible" class="global-player-root">
    <audio ref="audioRef" :src="store.currentStreamUrl"
      @timeupdate="onTimeUpdate" @loadedmetadata="onLoadedMetadata"
      @ended="onEnded" preload="metadata"></audio>

    <!-- ============ 展开状态 ============ -->
    <div v-if="store.isExpanded" class="player-expanded">
      <!-- 收起横条 -->
      <div class="player-grip" @click="store.toggleExpand()">
        <div class="grip-line"></div>
      </div>

      <!-- 播放器主体 / 播放列表 切换 -->
      <template v-if="!showPlaylist">
        <!-- 封面图 -->
        <div class="player-cover">
          <img v-if="store.coverUrl" :src="store.coverUrl" alt="cover" class="cover-img" />
          <div v-else class="cover-placeholder">
            <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
          </div>
        </div>

        <!-- 文件名 & 作品名 -->
        <div class="player-info">
          <div class="player-filename" :title="store.currentFile?.filename">
            {{ store.currentFile?.filename || '未知文件' }}
          </div>
          <div class="player-work-title" :title="store.workTitle">
            {{ store.workTitle || '未知作品' }}
          </div>
        </div>

        <!-- 进度条 -->
        <div class="player-progress-section">
          <div class="progress-bar-wrapper" @click="seekTo">
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" :style="{ width: store.progressPercent + '%' }"></div>
            </div>
            <div class="progress-bar-thumb" :style="{ left: store.progressPercent + '%' }"></div>
          </div>
          <div class="progress-times">
            <span>{{ formatTime(store.currentTime) }}</span>
            <span>{{ formatTime(store.duration) }}</span>
          </div>
        </div>

        <!-- 控制按钮 -->
        <div class="player-controls">
          <button class="ctrl-btn" :disabled="!store.hasPrev" @click="store.playPrev()">
            <SkipBack class="ctrl-icon fill-current" />
          </button>
          <button class="ctrl-btn" @click="skipBack5">
            <RotateCcw class="ctrl-icon-sm" />
            <span class="skip-label">5</span>
          </button>
          <button class="ctrl-btn-main" @click="store.togglePlay()">
            <Pause v-if="store.isPlaying" class="ctrl-icon-main fill-current" />
            <Play v-else class="ctrl-icon-main fill-current ml-0.5" />
          </button>
          <button class="ctrl-btn" @click="skipForward30">
            <RotateCw class="ctrl-icon-sm" />
            <span class="skip-label">30</span>
          </button>
          <button class="ctrl-btn" :disabled="!store.hasNext" @click="store.playNext()">
            <SkipForward class="ctrl-icon fill-current" />
          </button>
        </div>

        <!-- 音量控制 -->
        <div class="player-volume">
          <button class="volume-btn" @click="handleToggleMute">
            <component :is="getVolumeIcon()" class="w-4 h-4" />
          </button>
          <div class="volume-slider-wrapper">
            <input type="range" min="0" max="1" step="0.01"
              :value="store.isMuted ? 0 : store.volume"
              class="volume-slider" @input="onVolumeChange" />
            <div class="volume-slider-fill" :style="{ width: `${(store.isMuted ? 0 : store.volume) * 100}%` }"></div>
          </div>
        </div>
      </template>

      <!-- 播放列表视图 -->
      <template v-else>
        <div class="playlist-view">
          <div class="playlist-header">
            <div class="playlist-title">
              <Music class="w-4 h-4" />
              <span>播放列表</span>
              <span class="playlist-count">{{ store.playlist.length }}</span>
            </div>
          </div>
          <div class="playlist-items">
            <div v-for="(file, index) in store.playlist" :key="file.id"
              class="playlist-item" :class="{ active: index === store.currentIndex }"
              @click="handleClickTrack(index)">
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

      <!-- 底部工具栏 -->
      <div class="player-toolbar">
        <button class="toolbar-btn" :class="{ active: showPlaylist }" @click="togglePlaylist" title="播放列表">
          <List class="w-5 h-5" />
        </button>
      </div>
    </div>

    <!-- ============ 收起状态 (迷你条) ============ -->
    <div v-else class="player-mini">
      <div class="mini-progress-bg-fill" :style="{ width: store.progressPercent + '%' }"></div>
      <div class="mini-content" @click="store.toggleExpand()">
        <div class="mini-cover">
          <img v-if="store.coverUrl" :src="store.coverUrl" alt="cover" class="mini-cover-img" />
          <div v-else class="mini-cover-placeholder"></div>
        </div>
        <div class="mini-info">
          <div class="mini-filename">{{ store.currentFile?.filename || '未知文件' }}</div>
          <div class="mini-work-title">{{ store.workTitle || '' }}</div>
        </div>
      </div>
      <div class="mini-controls">
        <button class="mini-ctrl-btn" @click.stop="store.playPrev()" :disabled="!store.hasPrev">
          <SkipBack class="w-4 h-4 fill-current" />
        </button>
        <button class="mini-ctrl-btn-main" @click.stop="store.togglePlay()">
          <Pause v-if="store.isPlaying" class="w-5 h-5 fill-current" />
          <Play v-else class="w-5 h-5 fill-current ml-0.5" />
        </button>
        <button class="mini-ctrl-btn" @click.stop="store.playNext()" :disabled="!store.hasNext">
          <SkipForward class="w-4 h-4 fill-current" />
        </button>
        <button class="mini-ctrl-btn" @click.stop="showPlaylist = true; store.toggleExpand()"
          title="播放列表">
          <List class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.global-player-root { position: fixed; z-index: 9999; }

/* ========== 展开状态 ========== */
.player-expanded {
  position: fixed;
  bottom: 16px;
  right: 16px;
  width: 340px;
  background: linear-gradient(145deg, #1e1e2e, #2a2a3e);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.06);
  color: #e0e0e0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(20px);
  animation: slideUp 0.3s ease-out;
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.player-grip {
  display: flex; align-items: center; justify-content: center;
  padding: 8px 0; cursor: pointer; transition: background 0.2s;
}
.player-grip:hover { background: rgba(255,255,255,0.05); }
.grip-line {
  width: 36px; height: 4px; border-radius: 2px;
  background: rgba(255,255,255,0.2);
}

.player-cover {
  margin: 0 20px 12px; border-radius: 12px; overflow: hidden;
  aspect-ratio: 4 / 3; background: #333; box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
.cover-img { width: 100%; height: 100%; object-fit: cover; }
.cover-placeholder {
  width: 100%; height: 100%; display: flex;
  align-items: center; justify-content: center; color: #555;
}

.player-info { padding: 0 20px 8px; text-align: center; }
.player-filename {
  font-size: 14px; font-weight: 600; color: #fff;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.4;
}
.player-work-title {
  font-size: 12px; color: rgba(255,255,255,0.5);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px;
}

.player-progress-section { padding: 4px 20px 0; }
.progress-bar-wrapper {
  position: relative; height: 18px; cursor: pointer;
  display: flex; align-items: center;
}
.progress-bar-bg {
  width: 100%; height: 4px; background: rgba(255,255,255,0.12);
  border-radius: 2px; overflow: hidden; position: relative;
}
.progress-bar-fill {
  height: 100%; background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px; transition: width 0.1s linear;
}
.progress-bar-thumb {
  position: absolute; top: 50%; width: 12px; height: 12px;
  border-radius: 50%; background: #8b5cf6;
  transform: translate(-50%, -50%);
  box-shadow: 0 0 6px rgba(139,92,246,0.5);
  opacity: 0; transition: opacity 0.2s;
}
.progress-bar-wrapper:hover .progress-bar-thumb { opacity: 1; }
.progress-bar-wrapper:hover .progress-bar-bg { height: 5px; }
.progress-times {
  display: flex; justify-content: space-between;
  font-size: 11px; color: rgba(255,255,255,0.4); padding-top: 4px;
}

.player-controls {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; padding: 8px 20px 4px;
}
.ctrl-btn {
  position: relative; display: flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; border-radius: 50%; border: none;
  background: transparent; color: rgba(255,255,255,0.7); cursor: pointer; transition: all 0.2s;
}
.ctrl-btn:hover:not(:disabled) { color: #fff; background: rgba(255,255,255,0.08); }
.ctrl-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.ctrl-icon { width: 22px; height: 22px; }
.ctrl-icon-sm { width: 20px; height: 20px; }
.skip-label {
  position: absolute; font-size: 8px; font-weight: 700; color: inherit;
  top: 50%; left: 50%; transform: translate(-50%, -50%);
}
.ctrl-btn-main {
  display: flex; align-items: center; justify-content: center;
  width: 52px; height: 52px; border-radius: 50%; border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff;
  cursor: pointer; transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(99,102,241,0.4);
}
.ctrl-btn-main:hover { transform: scale(1.06); box-shadow: 0 6px 20px rgba(99,102,241,0.5); }
.ctrl-icon-main { width: 24px; height: 24px; }

.player-volume { display: flex; align-items: center; gap: 8px; padding: 4px 20px; }
.volume-btn {
  display: flex; align-items: center; justify-content: center;
  border: none; background: none; color: rgba(255,255,255,0.5);
  cursor: pointer; padding: 4px; border-radius: 4px; transition: color 0.2s;
}
.volume-btn:hover { color: #fff; }
.volume-slider-wrapper {
  flex: 1; position: relative; height: 4px; border-radius: 2px;
  background: rgba(255,255,255,0.12); overflow: hidden;
}
.volume-slider {
  position: absolute; inset: 0; width: 100%; height: 100%;
  opacity: 0; cursor: pointer; z-index: 2; margin: 0;
}
.volume-slider-fill {
  position: absolute; top: 0; left: 0; height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px; transition: width 0.1s linear; pointer-events: none;
}

/* ========== 播放列表视图（内嵌） ========== */
.playlist-view {
  flex: 1; display: flex; flex-direction: column;
  min-height: 0; max-height: 420px;
}
.playlist-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; border-bottom: 1px solid rgba(255,255,255,0.06); flex-shrink: 0;
}
.playlist-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 600; color: #fff;
}
.playlist-count {
  font-size: 11px; color: rgba(255,255,255,0.4);
  background: rgba(255,255,255,0.08); padding: 1px 8px; border-radius: 10px;
}
.playlist-items {
  flex: 1; overflow-y: auto; padding: 4px 0;
}
.playlist-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 20px; cursor: pointer; transition: background 0.15s;
}
.playlist-item:hover { background: rgba(255,255,255,0.05); }
.playlist-item.active { background: rgba(139,92,246,0.12); }
.item-icon {
  width: 24px; height: 24px; display: flex; align-items: center;
  justify-content: center; flex-shrink: 0; color: rgba(255,255,255,0.4);
}
.playlist-item.active .item-icon { color: #8b5cf6; }
.item-play-icon { opacity: 0; }
.playlist-item:hover .item-play-icon { opacity: 1; }
.item-info { flex: 1; min-width: 0; }
.item-name {
  font-size: 13px; color: rgba(255,255,255,0.7);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.playlist-item.active .item-name { color: #8b5cf6; font-weight: 500; }
.item-duration { font-size: 11px; color: rgba(255,255,255,0.3); flex-shrink: 0; }

/* 底部工具栏 */
.player-toolbar {
  display: flex; align-items: center; justify-content: center;
  gap: 16px; padding: 8px 20px 12px;
}
.toolbar-btn {
  display: flex; align-items: center; justify-content: center;
  border: none; background: none; color: rgba(255,255,255,0.4);
  cursor: pointer; padding: 6px; border-radius: 6px; transition: all 0.2s;
}
.toolbar-btn:hover { color: #fff; background: rgba(255,255,255,0.08); }
.toolbar-btn.active { color: #8b5cf6; }

/* ========== 收起状态 ========== */
.player-mini {
  position: fixed; bottom: 0; left: 0; right: 0;
  background: linear-gradient(180deg, #1e1e2e, #16162a);
  color: #e0e0e0; display: flex; align-items: center; flex-wrap: wrap;
  box-shadow: 0 -2px 16px rgba(0,0,0,0.3); z-index: 9999;
  animation: slideUpMini 0.25s ease-out;
}
@keyframes slideUpMini {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
.mini-progress-bg-fill {
  position: absolute; top: 0; left: 0; bottom: 0;
  background: rgba(139, 92, 246, 0.25);
  transition: width 0.1s linear; pointer-events: none; z-index: 0;
}
.mini-content {
  position: relative; z-index: 1;
  display: flex; align-items: center; gap: 10px;
  flex: 1; min-width: 0; padding: 6px 12px; cursor: pointer;
}
.mini-content:hover { background: rgba(255,255,255,0.03); }
.mini-cover {
  width: 40px; height: 40px; border-radius: 6px;
  overflow: hidden; flex-shrink: 0; background: #333;
}
.mini-cover-img { width: 100%; height: 100%; object-fit: cover; }
.mini-cover-placeholder { width: 100%; height: 100%; background: #444; }
.mini-info { flex: 1; min-width: 0; }
.mini-filename {
  font-size: 13px; font-weight: 500; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; color: #fff;
}
.mini-work-title {
  font-size: 11px; color: rgba(255,255,255,0.4);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.mini-controls {
  position: relative; z-index: 1;
  display: flex; align-items: center; gap: 4px; padding: 6px 12px; flex-shrink: 0;
}
.mini-ctrl-btn {
  display: flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: 50%; border: none;
  background: transparent; color: rgba(255,255,255,0.6); cursor: pointer; transition: all 0.2s;
}
.mini-ctrl-btn:hover:not(:disabled) { color: #fff; background: rgba(255,255,255,0.1); }
.mini-ctrl-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.mini-ctrl-btn.active { color: #8b5cf6; }
.mini-ctrl-btn-main {
  display: flex; align-items: center; justify-content: center;
  width: 36px; height: 36px; border-radius: 50%; border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff;
  cursor: pointer; transition: all 0.2s;
}
.mini-ctrl-btn-main:hover { transform: scale(1.08); }

@media (max-width: 640px) {
  .player-expanded { left: 8px; right: 8px; bottom: 8px; width: auto; }
}
</style>
