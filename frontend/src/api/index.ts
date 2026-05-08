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

export async function uploadFiles(workId: number, files: File[], targetPath?: string): Promise<FileUploadResponse> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }
  const params = targetPath ? { path: targetPath } : {}
  const { data } = await api.post(`/works/${workId}/files/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params,
  })
  return data
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
