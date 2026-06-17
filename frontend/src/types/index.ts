export interface Work {
  id: number
  rj_code: string
  title: string
  circle: string
  voice_actors: string[]
  release_date: string
  genres: string[]
  cover_url: string
  cover_path: string
  description: string
  series: string
  age_category: number
  file_count: number
  created_at: string
  updated_at: string
}

export interface WorkListItem {
  id: number
  rj_code: string
  title: string
  circle: string
  cover_path: string
  genres: string[]
  voice_actors: string[]
  file_count: number
  created_at: string
}

export interface FileItem {
  id: number
  work_id: number
  filename: string
  filepath: string
  file_size: number
  file_type: 'audio' | 'video' | 'image' | 'text' | 'pdf' | 'other'
  created_at: string
}

export interface FolderItem {
  type: 'folder'
  name: string
  path: string
}

export type DirEntry = FileItem | FolderItem

export interface Breadcrumb {
  name: string
  path: string
}

export interface DirectoryListing {
  current_path: string
  breadcrumbs: Breadcrumb[]
  entries: DirEntry[]
}

export interface FileUploadResponse {
  files: FileItem[]
  errors: string[]
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

export function getCoverUrl(coverPath: string): string {
  if (!coverPath) return ''
  return `/${coverPath}`
}

export function isFile(entry: DirEntry): entry is FileItem {
  return (entry as any).type !== 'folder' && 'file_type' in entry
}

export function isFolder(entry: DirEntry): entry is FolderItem {
  return (entry as any).type === 'folder'
}

// ========== 存储设置相关 ==========

export interface StorageSettings {
  webdav_enabled: boolean
  webdav_url: string
  webdav_username: string
  /** 密码读取时返回 "***"（已设置）或 ""（未设置）；写入时空/"***"表示保持原值 */
  webdav_password: string
  webdav_base_path: string
  /** 新作品默认落点 "local" | "webdav" */
  default_target: string
}

export interface BrowseEntry {
  name: string
  path: string
}

export interface TestConnectionResult {
  ok: boolean
  message: string
}

export interface ScanResult {
  new_count: number
  total: number
}
