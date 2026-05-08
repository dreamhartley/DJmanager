"""Pydantic 请求/响应模型"""

from datetime import datetime
from pydantic import BaseModel, Field


# ========== 作品相关 ==========

class WorkCreate(BaseModel):
    """添加作品请求"""
    rj_code: str = Field(..., min_length=2, max_length=20, description="DLsite RJ编号，如 RJ01553954")


class WorkResponse(BaseModel):
    """作品响应"""
    id: int
    rj_code: str
    title: str
    circle: str
    voice_actors: list[str]
    release_date: str
    genres: list[str]
    cover_url: str
    cover_path: str
    description: str
    series: str
    age_category: int
    file_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkListResponse(BaseModel):
    """作品列表响应"""
    id: int
    rj_code: str
    title: str
    circle: str
    cover_path: str
    genres: list[str] = []
    voice_actors: list[str] = []
    file_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ========== 文件相关 ==========

class FileResponse(BaseModel):
    """文件响应"""
    id: int
    work_id: int
    filename: str
    filepath: str
    file_size: int
    file_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FileRenameRequest(BaseModel):
    """重命名请求"""
    new_name: str = Field(..., min_length=1, max_length=500)


class FileCopyRequest(BaseModel):
    """复制/移动文件请求"""
    file_ids: list[int] = Field(..., min_length=1)
    target_work_id: int


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    file_ids: list[int] = Field(..., min_length=1)


class FileUploadResponse(BaseModel):
    """上传响应"""
    files: list[FileResponse]
    errors: list[str] = []


# ========== 文件夹相关 ==========

class FolderEntry(BaseModel):
    """文件夹条目"""
    type: str = "folder"
    name: str
    path: str  # 相对于作品根目录的路径

class DirEntry(BaseModel):
    """目录条目（文件或文件夹）"""
    type: str  # "file" | "folder"
    # 文件属性（仅当 type=file 时有效）
    id: int | None = None
    work_id: int | None = None
    filename: str | None = None
    filepath: str | None = None
    file_size: int | None = None
    file_type: str | None = None
    created_at: datetime | None = None
    # 文件夹属性（仅当 type=folder 时有效）
    name: str | None = None
    path: str | None = None

class DirectoryListing(BaseModel):
    """目录列表响应"""
    current_path: str
    breadcrumbs: list[dict]
    entries: list[DirEntry]

class CreateFolderRequest(BaseModel):
    """创建文件夹请求"""
    folder_name: str = Field(..., min_length=1, max_length=255)

class RenameFolderRequest(BaseModel):
    """重命名文件夹请求"""
    current_path: str = Field(..., min_length=1, description="文件夹相对于作品根目录的路径")
    new_name: str = Field(..., min_length=1, max_length=255)
