import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { WorkListItem } from '../types'
import { listWorks } from '../api'

export const useWorksStore = defineStore('works', () => {
  const works = ref<WorkListItem[]>([])
  const loading = ref(false)

  async function fetchWorks() {
    loading.value = true
    try {
      works.value = await listWorks()
    } finally {
      loading.value = false
    }
  }

  return { works, loading, fetchWorks }
})
