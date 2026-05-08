<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Play, Pause, Volume2, VolumeX, SkipBack, SkipForward, Repeat, Shuffle } from 'lucide-vue-next'

const props = defineProps<{
  src: string
  filename: string
}>()

const audioRef = ref<HTMLAudioElement | null>(null)
const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(1)
const isMuted = ref(false)

function togglePlay() {
  if (!audioRef.value) return
  if (audioRef.value.paused) {
    audioRef.value.play()
    playing.value = true
  } else {
    audioRef.value.pause()
    playing.value = false
  }
}

function onTimeUpdate() {
  if (audioRef.value) currentTime.value = audioRef.value.currentTime
}

function onLoadedMetadata() {
  if (audioRef.value) duration.value = audioRef.value.duration
}

function onSeek(e: Event) {
  const input = e.target as HTMLInputElement
  if (audioRef.value) {
    audioRef.value.currentTime = Number(input.value)
    currentTime.value = Number(input.value)
  }
}

function onVolumeChange(e: Event) {
  const input = e.target as HTMLInputElement
  volume.value = Number(input.value)
  if (audioRef.value) {
    audioRef.value.volume = volume.value
    isMuted.value = volume.value === 0
  }
}

function toggleMute() {
  if (!audioRef.value) return
  isMuted.value = !isMuted.value
  audioRef.value.muted = isMuted.value
  if (isMuted.value) {
    audioRef.value.volume = 0
  } else {
    audioRef.value.volume = volume.value || 1
  }
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function onEnded() {
  playing.value = false
}

// 自动播放
onMounted(() => {
  if (audioRef.value) {
    audioRef.value.play().catch(() => {
      // 忽略自动播放失败
    })
  }
})
</script>

<template>
  <div class="p-6 bg-white rounded-lg shadow-sm border border-gray-200">
    <audio
      ref="audioRef"
      :src="src"
      @timeupdate="onTimeUpdate"
      @loadedmetadata="onLoadedMetadata"
      @ended="onEnded"
      @play="playing = true"
      @pause="playing = false"
      preload="metadata"
    ></audio>

    <div class="flex flex-col gap-6">
      <!-- 标题 -->
      <div class="text-center">
        <h3 class="text-lg font-medium text-gray-900 truncate px-4" :title="filename">{{ filename }}</h3>
        <p class="text-sm text-gray-500 mt-1">正在播放</p>
      </div>

      <!-- 进度条 -->
      <div class="w-full flex items-center gap-3 px-4">
        <span class="text-xs text-gray-500 w-10 text-right font-medium">{{ formatTime(currentTime) }}</span>
        <div class="relative flex-1 h-2 group cursor-pointer">
          <input
            type="range"
            :min="0"
            :max="duration || 0"
            :value="currentTime"
            class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
            @input="onSeek"
          />
          <div class="absolute inset-0 bg-gray-200 rounded-full overflow-hidden">
            <div 
              class="h-full bg-blue-500 transition-all duration-100"
              :style="{ width: `${(currentTime / (duration || 1)) * 100}%` }"
            ></div>
          </div>
          <!-- 滑块圆点 -->
          <div 
            class="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-blue-600 rounded-full shadow-sm opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
            :style="{ left: `calc(${(currentTime / (duration || 1)) * 100}% - 6px)` }"
          ></div>
        </div>
        <span class="text-xs text-gray-500 w-10 font-medium">{{ formatTime(duration) }}</span>
      </div>

      <!-- 控制区 -->
      <div class="flex items-center justify-between px-4">
        <!-- 左侧控制 (循环/随机) -->
        <div class="flex items-center gap-4 w-24">
          <button class="text-gray-400 hover:text-blue-500 transition-colors">
            <Shuffle class="w-5 h-5" />
          </button>
          <button class="text-gray-400 hover:text-blue-500 transition-colors">
            <Repeat class="w-5 h-5" />
          </button>
        </div>

        <!-- 主控制按钮 -->
        <div class="flex items-center gap-6">
          <button class="text-gray-600 hover:text-blue-600 transition-colors">
            <SkipBack class="w-6 h-6 fill-current" />
          </button>
          
          <button
            class="w-14 h-14 rounded-full bg-blue-500 hover:bg-blue-600 text-white flex items-center justify-center transition-all shadow-md hover:shadow-lg hover:scale-105"
            @click="togglePlay"
          >
            <Pause v-if="playing" class="w-6 h-6 fill-current" />
            <Play v-else class="w-6 h-6 fill-current ml-1" />
          </button>

          <button class="text-gray-600 hover:text-blue-600 transition-colors">
            <SkipForward class="w-6 h-6 fill-current" />
          </button>
        </div>

        <!-- 音量控制 -->
        <div class="flex items-center gap-2 w-32 justify-end group">
          <button @click="toggleMute" class="text-gray-500 hover:text-blue-500 transition-colors">
            <VolumeX v-if="isMuted || volume === 0" class="w-5 h-5" />
            <Volume2 v-else class="w-5 h-5" />
          </button>
          <div class="relative w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden cursor-pointer">
            <input
              type="range"
              :min="0"
              :max="1"
              step="0.01"
              :value="isMuted ? 0 : volume"
              class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
              @input="onVolumeChange"
            />
            <div 
              class="h-full bg-blue-400 transition-all duration-100"
              :style="{ width: `${(isMuted ? 0 : volume) * 100}%` }"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
