<script setup lang="ts">
import type { WorkListItem } from '../types'
import { getCoverUrl } from '../types'

const props = defineProps<{
  work: WorkListItem
}>()

const emit = defineEmits<{
  delete: [id: number]
}>()

const coverUrl = getCoverUrl(props.work.cover_path)
</script>

<template>
  <router-link
    :to="`/work/${work.rj_code}`"
    class="group relative bg-white rounded-lg overflow-hidden border border-gray-200 hover:shadow-md transition-all duration-200 flex flex-col h-full"
  >
    <!-- 封面图 -->
    <div class="aspect-[4/3] overflow-hidden bg-gray-100 relative">
      <img
        v-if="coverUrl"
        :src="coverUrl"
        :alt="work.title"
        class="w-full h-full object-cover"
        loading="lazy"
      />
      <div v-else class="w-full h-full flex items-center justify-center text-gray-400">
        <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
    </div>

    <!-- 信息栏 -->
    <div class="p-3 flex flex-col flex-1">
      <h3 class="text-sm font-medium text-gray-900 line-clamp-2 mb-2 group-hover:text-blue-600 transition-colors" :title="work.title || work.rj_code">
        {{ work.title || work.rj_code }}
      </h3>
      
      <!-- 标签区域 -->
      <div class="flex flex-col gap-1.5">
        <div v-if="work.genres && work.genres.length > 0" class="flex flex-wrap gap-1">
          <span 
            v-for="(tag, index) in work.genres.slice(0, 5)" 
            :key="index"
            class="text-[10px] px-1.5 py-0.5 rounded-full whitespace-nowrap bg-gray-200 text-gray-700"
          >
            {{ tag }}
          </span>
        </div>
        <div v-if="work.voice_actors && work.voice_actors.length > 0" class="flex flex-wrap gap-1">
          <span 
            v-for="(actor, index) in work.voice_actors.slice(0, 3)" 
            :key="'actor-'+index"
            class="text-[10px] px-1.5 py-0.5 rounded-full whitespace-nowrap bg-green-500 text-white"
          >
            {{ actor }}
          </span>
        </div>
      </div>
    </div>

    <!-- 删除按钮 -->
    <button
      class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-full bg-red-500/80 hover:bg-red-600 text-white z-10"
      title="删除作品"
      @click.prevent.stop="emit('delete', work.id)"
    >
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </router-link>
</template>
