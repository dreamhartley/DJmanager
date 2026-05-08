import axios from 'axios'
import type { Work, WorkListItem, FileItem, DirectoryListing, DirEntry, FileUploadResponse } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// ========== 作品 API ==========

export async function addWork(rjCode: string): Promise<Work> {
  const { data } = await api.post('/works', { rj_code: rjCode })
  return data
}

export async function listWorks(): Promise<WorkListItem[]> {
  const { data } = await api.get('/works')
  return data
}

export async function getWork(rjCode: string): Promise<Work> {
  const { data } = await api.get(`/works/${rjCode}`)
  return data
}

export async function deleteWork(id: number): Promise<void> {
  await api.delete(`/works/${id}`)
}

// ========== 目录 API ==========

export async function listDirectory(workId: number, path?: string): Promise<DirectoryListing> {
  const params = path ? { path } : {}
  const { data } = await api.get(`/works/${workId}/directory`, { params })
  return data
}

// ========== 文件 API ==========

// ========== Cloudflare 分块上传支持 ==========

interface CfCheckResult {
  is_cloudflare: boolean
  chunk_size: number
  chunk_threshold: number
}

interface UploadProgress {
  /** 当前文件名 */
  filename: string
  /** 当前文件的分块进度（仅分块上传时有效） */
  chunkIndex?: number
  chunkTotal?: number
}

let _cfCheckCache: CfCheckResult | null = null

async function checkCloudflare(): Promise<CfCheckResult> {
  if (_cfCheckCache) return _cfCheckCache
  try {
    const { data } = await api.get('/upload/check-cf')
    _cfCheckCache = data
    return data
  } catch {
    // 检测失败时不启用分块
    return { is_cloudflare: false, chunk_size: 80 * 1024 * 1024, chunk_threshold: 100 * 1024 * 1024 }
  }
}

async function uploadFileChunked(
  workId: number,
  file: File,
  targetPath?: string,
  onProgress?: (p: UploadProgress) => void,
): Promise<FileUploadResponse> {
  const cfInfo = await checkCloudflare()
  const chunkSize = cfInfo.chunk_size

  const totalChunks = Math.ceil(file.size / chunkSize)

  // 1. 初始化分块上传
  const { data: initData } = await api.post('/upload/init', null, {
    params: {
      work_id: workId,
      filename: file.name,
      total_size: file.size,
      total_chunks: totalChunks,
      path: targetPath || '',
    },
  })

  const uploadId: string = initData.upload_id

  try {
    // 2. 逐块上传
    for (let i = 0; i < totalChunks; i++) {
      const start = i * chunkSize
      const end = Math.min(start + chunkSize, file.size)
      const blob = file.slice(start, end)

      const chunkForm = new FormData()
      chunkForm.append('chunk', blob, `chunk_${i}`)

      onProgress?.({
        filename: file.name,
        chunkIndex: i + 1,
        chunkTotal: totalChunks,
      })

      await api.post('/upload/chunk', chunkForm, {
        params: { upload_id: uploadId, chunk_index: i },
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000, // 5分钟超时 - 大文件分块可能需要更久
      })
    }

    // 3. 合并分块
    const { data: completeData } = await api.post('/upload/complete', null, {
      params: { upload_id: uploadId },
      timeout: 300000,
    })

    return completeData
  } catch (e) {
    // 出错时取消上传、清理服务端临时文件
    try {
      await api.delete(`/upload/${uploadId}`)
    } catch { /* ignore cleanup errors */ }
    throw e
  }
}

export async function uploadFiles(
  workId: number,
  files: File[],
  targetPath?: string,
  onProgress?: (p: UploadProgress) => void,
): Promise<FileUploadResponse> {
  const cfInfo = await checkCloudflare()
  const needsChunked = cfInfo.is_cloudflare

  const allUploaded: FileItem[] = []
  const allErrors: string[] = []

  for (const file of files) {
    try {
      if (needsChunked && file.size > cfInfo.chunk_threshold) {
        // 大文件 + Cloudflare → 分块上传
        const result = await uploadFileChunked(workId, file, targetPath, onProgress)
        allUploaded.push(...result.files)
        allErrors.push(...result.errors)
      } else {
        // 小文件或非 Cloudflare → 直接上传
        onProgress?.({ filename: file.name })
        const formData = new FormData()
        formData.append('files', file)
        const params = targetPath ? { path: targetPath } : {}
        const { data } = await api.post(`/works/${workId}/files/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          params,
          timeout: 300000,
        })
        allUploaded.push(...data.files)
        allErrors.push(...data.errors)
      }
    } catch (e: any) {
      allErrors.push(`${file.name}: ${e.message || e}`)
    }
  }

  return { files: allUploaded, errors: allErrors }
}

export async function deleteFile(fileId: number): Promise<void> {
  await api.delete(`/files/${fileId}`)
}

export async function batchDeleteFiles(fileIds: number[]): Promise<void> {
  await api.post('/files/batch-delete', { file_ids: fileIds })
}

export async function renameFile(fileId: number, newName: string): Promise<FileItem> {
  const { data } = await api.patch(`/files/${fileId}/rename`, { new_name: newName })
  return data
}

export async function copyFiles(fileIds: number[], targetWorkId: number): Promise<FileItem[]> {
  const { data } = await api.post('/files/copy', { file_ids: fileIds, target_work_id: targetWorkId })
  return data
}

export async function moveFiles(fileIds: number[], targetWorkId: number): Promise<FileItem[]> {
  const { data } = await api.post('/files/move', { file_ids: fileIds, target_work_id: targetWorkId })
  return data
}

// ========== 文件夹 API ==========

export async function createFolder(workId: number, folderName: string, parentPath?: string): Promise<void> {
  const params = parentPath ? { path: parentPath } : {}
  await api.post(`/works/${workId}/folders`, { folder_name: folderName }, { params })
}

export async function deleteFolder(workId: number, folderPath: string): Promise<void> {
  await api.delete(`/works/${workId}/folders`, { params: { path: folderPath } })
}

export async function renameFolder(workId: number, currentPath: string, newName: string): Promise<void> {
  await api.patch(`/works/${workId}/folders/rename`, { current_path: currentPath, new_name: newName })
}

// ========== 流媒体 & 预览 ==========

export function getStreamUrl(fileId: number): string {
  return `/api/files/${fileId}/stream`
}

export function getPreviewUrl(fileId: number): string {
  return `/api/files/${fileId}/preview`
}
