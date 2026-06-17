import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { WorkListItem } from '../types'
import { listWorks } from '../api'

export const useWorksStore = defineStore('works', () => {
  const works = ref<WorkListItem[]>([])
  const loading = ref(false)

  // 主界面分页状态（跨路由持久化，便于从详情页返回时恢复）
  const homePage = ref(1)
  const homeScrollTop = ref(0)

  async function fetchWorks() {
    loading.value = true
    try {
      works.value = await listWorks()
    } finally {
      loading.value = false
    }
  }

  function setHomeState(page: number, scrollTop: number) {
    homePage.value = page
    homeScrollTop.value = scrollTop
  }

  return { works, loading, fetchWorks, homePage, homeScrollTop, setHomeState }
})
