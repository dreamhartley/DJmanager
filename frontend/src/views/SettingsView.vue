<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  getStorageSettings,
  saveStorageSettings,
  testStorageConnection,
  browseStorageFolders,
} from '../api'
import type { StorageSettings, BrowseEntry, TestConnectionResult } from '../types'
import {
  ChevronLeft, Folder, FolderOpen, Loader2, CheckCircle2, XCircle, X, RefreshCw,
} from 'lucide-vue-next'

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const settings = ref<StorageSettings>({
  webdav_enabled: false,
  webdav_url: '',
  webdav_username: '',
  webdav_password: '',
  webdav_base_path: '',
  default_target: 'webdav',
})
// 密码是否来自服务端的掩码（未修改）
const passwordMasked = ref(false)

const message = ref<{ type: 'success' | 'error'; text: string } | null>(null)
const testResult = ref<TestConnectionResult | null>(null)

// 目录浏览器状态
const browsing = ref(false)
const browsePath = ref('')
const browseEntries = ref<BrowseEntry[]>([])
const browseLoading = ref(false)
const browseError = ref('')

onMounted(async () => {
  await loadSettings()
})

async function loadSettings() {
  loading.value = true
  try {
    const s = await getStorageSettings()
    settings.value = s
    passwordMasked.value = s.webdav_password === '***'
  } catch (e: any) {
    message.value = { type: 'error', text: `加载配置失败：${e.message || e}` }
  } finally {
    loading.value = false
  }
}

function clearMessage() {
  message.value = null
}

async function handleSave() {
  clearMessage()
  testResult.value = null
  saving.value = true
  try {
    // 密码未修改（仍为掩码）时传空，后端会保持原值
    const payload: StorageSettings = { ...settings.value }
    if (passwordMasked.value && settings.value.webdav_password === '***') {
      payload.webdav_password = ''
    }
    const saved = await saveStorageSettings(payload)
    settings.value = saved
    passwordMasked.value = saved.webdav_password === '***'
    message.value = { type: 'success', text: '配置已保存并即时生效' }
  } catch (e: any) {
    message.value = { type: 'error', text: `保存失败：${e.message || e}` }
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  clearMessage()
  testResult.value = null
  if (!settings.value.webdav_url) {
    testResult.value = { ok: false, message: 'URL 不能为空' }
    return
  }
  testing.value = true
  try {
    // 用表单当前值测试（密码未改时使用掩码，后端 test 用临时凭据，掩码会失败 → 提示先保存）
    const pwd = passwordMasked.value && settings.value.webdav_password === '***'
      ? '' : settings.value.webdav_password
    testResult.value = await testStorageConnection({
      url: settings.value.webdav_url,
      username: settings.value.webdav_username,
      password: pwd,
      base_path: settings.value.webdav_base_path,
    })
  } catch (e: any) {
    testResult.value = { ok: false, message: `请求失败：${e.message || e}` }
  } finally {
    testing.value = false
  }
}

// ========== 目录浏览器 ==========

function openBrowser() {
  browsing.value = true
  // 始终从 WebDAV 服务根开始浏览（后端 browse 操作的是相对服务根的路径，
  // 而非已保存的 base_path），这样用户能浏览到 base_path 之上/之外的目录。
  browsePath.value = ''
  browseEntries.value = []
  browseError.value = ''
  loadBrowse()
}

async function loadBrowse() {
  browseLoading.value = true
  browseError.value = ''
  try {
    browseEntries.value = await browseStorageFolders(browsePath.value)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e.message || e
    browseError.value = `浏览失败：${detail}`
  } finally {
    browseLoading.value = false
  }
}

function enterDir(entry: BrowseEntry) {
  browsePath.value = entry.path
  loadBrowse()
}

function goUp() {
  const parts = browsePath.value.split('/').filter(Boolean)
  parts.pop()
  browsePath.value = parts.join('/')
  loadBrowse()
}

function selectCurrentDir() {
  settings.value.webdav_base_path = browsePath.value
  browsing.value = false
}

function closeBrowser() {
  browsing.value = false
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <!-- 返回 + 标题 -->
    <div class="flex items-center gap-3 mb-6">
      <router-link to="/" class="p-2 hover:bg-gray-200 rounded-lg transition-colors" title="返回首页">
        <ChevronLeft class="w-5 h-5 text-gray-600" />
      </router-link>
      <h1 class="text-2xl font-bold text-gray-900">存储设置</h1>
    </div>

    <!-- 提示条 -->
    <div v-if="message" class="mb-4 p-3 rounded-lg flex items-center gap-2 text-sm"
      :class="message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'">
      <CheckCircle2 v-if="message.type === 'success'" class="w-5 h-5 flex-shrink-0" />
      <XCircle v-else class="w-5 h-5 flex-shrink-0" />
      <span class="flex-1">{{ message.text }}</span>
      <button class="text-current opacity-60 hover:opacity-100" @click="clearMessage">
        <X class="w-4 h-4" />
      </button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-8 h-8 text-blue-500 animate-spin" />
    </div>

    <div v-else class="bg-white rounded-lg border border-gray-200 shadow-sm p-6 space-y-6">
      <!-- 启用开关 -->
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold text-gray-900">WebDAV 存储</h2>
          <p class="text-sm text-gray-500 mt-1">启用后，新作品可保存到 WebDAV；本地已存在的作品仍优先使用本地。</p>
        </div>
        <button
          type="button"
          role="switch"
          :aria-checked="settings.webdav_enabled"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
          :class="settings.webdav_enabled ? 'bg-blue-500' : 'bg-gray-300'"
          @click="settings.webdav_enabled = !settings.webdav_enabled"
        >
          <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
            :class="settings.webdav_enabled ? 'translate-x-6' : 'translate-x-1'" />
        </button>
      </div>

      <div class="border-t border-gray-100" />

      <!-- 配置表单 -->
      <div :class="{ 'opacity-50 pointer-events-none': !settings.webdav_enabled }" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">WebDAV URL</label>
          <input
            v-model="settings.webdav_url"
            type="text"
            placeholder="https://dav.example.com"
            class="w-full px-3 py-2 border border-gray-300 focus:border-blue-500 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
          />
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">用户名</label>
            <input
              v-model="settings.webdav_username"
              type="text"
              autocomplete="off"
              class="w-full px-3 py-2 border border-gray-300 focus:border-blue-500 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
            <input
              v-model="settings.webdav_password"
              type="password"
              autocomplete="new-password"
              :placeholder="passwordMasked ? '（已设置，留空保持不变）' : '请输入密码'"
              class="w-full px-3 py-2 border border-gray-300 focus:border-blue-500 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
          </div>
        </div>

        <!-- 作品根目录 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">作品根目录（base_path）</label>
          <div class="flex gap-2">
            <input
              v-model="settings.webdav_base_path"
              type="text"
              placeholder="WebDAV 上对应 data/works 的目录，如 DJmanager/works"
              class="flex-1 px-3 py-2 border border-gray-300 focus:border-blue-500 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
            <button
              type="button"
              class="px-3 py-2 border border-gray-300 hover:bg-gray-50 rounded-lg text-gray-700 text-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
              :disabled="!settings.webdav_enabled || !settings.webdav_url"
              @click="openBrowser"
            >
              <FolderOpen class="w-4 h-4" />
              浏览
            </button>
          </div>
          <p class="text-xs text-gray-400 mt-1">指定的目录下可放置 RJ 文件夹，结构与本地 data/works 一致。</p>
        </div>

        <!-- 新作品默认落点 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">新作品默认保存位置</label>
          <div class="flex gap-3">
            <label class="flex items-center gap-2 px-4 py-2 border rounded-lg cursor-pointer transition-colors"
              :class="settings.default_target === 'local' ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-300 text-gray-700 hover:bg-gray-50'">
              <input type="radio" value="local" v-model="settings.default_target" class="text-blue-500" />
              <span class="text-sm">本地</span>
            </label>
            <label class="flex items-center gap-2 px-4 py-2 border rounded-lg cursor-pointer transition-colors"
              :class="settings.default_target === 'webdav' ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-300 text-gray-700 hover:bg-gray-50'">
              <input type="radio" value="webdav" v-model="settings.default_target" class="text-blue-500" />
              <span class="text-sm">WebDAV（节省本地空间）</span>
            </label>
          </div>
        </div>
      </div>

      <!-- 测试结果 -->
      <div v-if="testResult" class="p-3 rounded-lg flex items-center gap-2 text-sm"
        :class="testResult.ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'">
        <CheckCircle2 v-if="testResult.ok" class="w-5 h-5 flex-shrink-0" />
        <XCircle v-else class="w-5 h-5 flex-shrink-0" />
        <span>{{ testResult.message }}</span>
      </div>

      <!-- 操作按钮 -->
      <div class="flex justify-end gap-3 border-t border-gray-100 pt-4">
        <button
          class="px-4 py-2 text-sm border border-gray-300 hover:bg-gray-50 rounded-lg text-gray-700 font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
          :disabled="testing || !settings.webdav_enabled"
          @click="handleTest"
        >
          <Loader2 v-if="testing" class="w-4 h-4 animate-spin" />
          <RefreshCw v-else class="w-4 h-4" />
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
        <button
          class="px-4 py-2 text-sm bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-lg shadow-sm transition-colors disabled:opacity-50 flex items-center gap-1.5"
          :disabled="saving"
          @click="handleSave"
        >
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>

  <!-- 目录浏览器 Modal -->
  <Teleport to="body">
    <div v-if="browsing" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="closeBrowser">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 flex flex-col max-h-[80vh]">
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 class="text-base font-semibold text-gray-900">选择作品根目录</h3>
          <button class="text-gray-400 hover:text-gray-600" @click="closeBrowser">
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- 面包屑 -->
        <div class="flex items-center gap-1 px-5 py-2 border-b border-gray-100 text-sm text-gray-600 overflow-x-auto">
          <button class="hover:text-blue-600 flex items-center gap-1" @click="browsePath = ''; loadBrowse()">
            <Folder class="w-4 h-4" />
            根
          </button>
          <template v-for="(part, i) in browsePath.split('/').filter(Boolean)" :key="i">
            <span class="text-gray-300">/</span>
            <button
              class="hover:text-blue-600"
              @click="browsePath = browsePath.split('/').filter(Boolean).slice(0, i + 1).join('/'); loadBrowse()"
            >{{ part }}</button>
          </template>
        </div>

        <!-- 列表 -->
        <div class="flex-1 overflow-y-auto px-2 py-2 min-h-[200px]">
          <div v-if="browseLoading" class="flex items-center justify-center py-10">
            <Loader2 class="w-6 h-6 text-blue-500 animate-spin" />
          </div>
          <div v-else-if="browseError" class="px-3 py-6 text-center text-sm text-red-500">{{ browseError }}</div>
          <div v-else-if="browseEntries.length === 0" class="px-3 py-6 text-center text-sm text-gray-400">该目录下没有子文件夹</div>
          <ul v-else class="space-y-0.5">
            <li v-if="browsePath">
              <button class="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 text-gray-600 text-sm"
                @click="goUp">
                <ChevronLeft class="w-4 h-4" />
                返回上级
              </button>
            </li>
            <li v-for="entry in browseEntries" :key="entry.path">
              <button class="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 text-gray-700 text-sm text-left"
                @click="enterDir(entry)">
                <Folder class="w-4 h-4 text-blue-400 flex-shrink-0" />
                <span class="truncate">{{ entry.name }}</span>
              </button>
            </li>
          </ul>
        </div>

        <div class="flex items-center justify-between gap-3 px-5 py-4 border-t border-gray-100">
          <span class="text-xs text-gray-400 truncate">当前：{{ browsePath || '（根目录）' }}</span>
          <div class="flex gap-2">
            <button class="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors" @click="closeBrowser">取消</button>
            <button class="px-3 py-1.5 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors" @click="selectCurrentDir">选择此目录</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
