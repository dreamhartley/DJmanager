"""文件管理 API 路由"""

import os
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Query
from fastapi.responses import StreamingResponse, FileResponse as StarletteFileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import WORKS_DIR, STREAM_CHUNK_SIZE, AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, IMAGE_EXTENSIONS, TEXT_EXTENSIONS
from database import get_db
from models import Work, File
from schemas import (
    FileResponse, FileRenameRequest, FileCopyRequest,
    BatchDeleteRequest, FileUploadResponse,
    DirEntry, DirectoryListing,
    CreateFolderRequest, RenameFolderRequest,
)
from services.file_manager import file_manager

router = APIRouter(prefix="/api", tags=["文件管理"])


def _file_to_response(f: File) -> FileResponse:
    return FileResponse(
        id=f.id,
        work_id=f.work_id,
        filename=f.filename,
        filepath=f.filepath,
        file_size=f.file_size,
        file_type=f.file_type,
        created_at=f.created_at,
    )


def _normalize_path(p: str) -> str:
    """规范化路径：统一使用正斜杠，去除首尾空格和斜杠。"""
    return p.replace("\\", "/").strip("/")


def _build_breadcrumbs(subpath: str) -> list[dict]:
    """根据子路径构建面包屑列表。subpath 相对于作品根目录。"""
    crumbs = [{"name": "ROOT", "path": ""}]
    normalized = _normalize_path(subpath)
    if normalized:
        parts = normalized.split("/")
        accumulated = ""
        for part in parts:
            if not part:
                continue
            accumulated = f"{accumulated}/{part}" if accumulated else part
            crumbs.append({"name": part, "path": accumulated})
    return crumbs


def _get_work_dir_relative_path(rj_code: str, relative_path: str) -> str:
    """获取相对于作品根目录的路径（去掉 rj_code 前缀）。"""
    normalized = relative_path.replace("\\", "/")
    prefix = f"{rj_code}/"
    if normalized.startswith(prefix):
        return normalized[len(prefix):]
    return normalized


# ========== 目录列表 ==========

@router.get("/works/{work_id}/directory", response_model=DirectoryListing)
async def list_directory(
    work_id: int,
    path: str = Query(default="", description="相对于作品根目录的子路径"),
    db: AsyncSession = Depends(get_db),
):
    """获取目录内容（文件 + 文件夹）"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    # 规范化 path（统一正斜杠，去除首尾/）
    subpath = _normalize_path(path)

    # 获取目录中的文件和文件夹
    file_paths, folder_paths = file_manager.list_directory(work.rj_code, subpath)

    # 查找文件对应的 DB 记录
    # 构建反斜杠版本用于匹配旧 DB 记录（Windows 历史数据）
    file_paths_backslash = [fp.replace("/", "\\") for fp in file_paths]
    all_lookup_paths = file_paths + file_paths_backslash
    file_records_map = {}
    if all_lookup_paths:
        result = await db.execute(
            select(File).where(File.work_id == work_id, File.filepath.in_(all_lookup_paths))
        )
        for f in result.scalars().all():
            # 用正斜杠版本作为 key，确保后续查找一致
            file_records_map[f.filepath.replace("\\", "/")] = f

    entries = []

    # 先添加文件夹
    for fp in folder_paths:
        folder_name = os.path.basename(fp)
        rel_to_work = _get_work_dir_relative_path(work.rj_code, fp)
        entries.append(DirEntry(
            type="folder",
            name=folder_name,
            path=rel_to_work,
        ))

    # 再添加文件
    for fp in file_paths:
        record = file_records_map.get(fp)
        if record:
            entries.append(DirEntry(
                type="file",
                id=record.id,
                work_id=record.work_id,
                filename=record.filename,
                filepath=record.filepath,
                file_size=record.file_size,
                file_type=record.file_type,
                created_at=record.created_at,
            ))
        else:
            # 孤立文件（磁盘上有但 DB 中没有）
            entries.append(DirEntry(
                type="file",
                filename=os.path.basename(fp),
                filepath=fp,
                file_size=0,
                file_type=file_manager.get_file_type(os.path.splitext(fp)[1]),
            ))

    breadcrumbs = _build_breadcrumbs(subpath)

    return DirectoryListing(
        current_path=subpath,
        breadcrumbs=breadcrumbs,
        entries=entries,
    )


# ========== 上传文件 ==========

@router.post("/works/{work_id}/files/upload", response_model=FileUploadResponse)
async def upload_files(
    work_id: int,
    files: list[UploadFile] = FastAPIFile(...),
    path: str = Query(default="", description="目标子目录（相对于作品根目录）"),
    db: AsyncSession = Depends(get_db),
):
    """上传文件到作品（可指定子目录）"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    subfolder = _normalize_path(path)
    uploaded = []
    errors = []

    for upload_file in files:
        try:
            content = await upload_file.read()
            relative_path, file_size = file_manager.save_uploaded_file(
                work.rj_code, upload_file.filename, content, subfolder
            )
            ext = os.path.splitext(upload_file.filename)[1]
            file_type = file_manager.get_file_type(ext)

            file_record = File(
                work_id=work_id,
                filename=upload_file.filename,
                filepath=relative_path,
                file_size=file_size,
                file_type=file_type,
            )
            db.add(file_record)
            await db.flush()
            await db.refresh(file_record)
            uploaded.append(_file_to_response(file_record))
        except Exception as e:
            errors.append(f"{upload_file.filename}: {e}")

    return FileUploadResponse(files=uploaded, errors=errors)


# ========== 文件夹 CRUD ==========

@router.post("/works/{work_id}/folders")
async def create_folder(
    work_id: int,
    data: CreateFolderRequest,
    path: str = Query(default="", description="父目录路径（相对于作品根目录）"),
    db: AsyncSession = Depends(get_db),
):
    """创建文件夹"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    subpath = _normalize_path(path)
    try:
        folder_rel_path = file_manager.create_folder(work.rj_code, subpath, data.folder_name)
        rel_to_work = _get_work_dir_relative_path(work.rj_code, folder_rel_path)
        return {"type": "folder", "name": data.folder_name, "path": rel_to_work}
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/works/{work_id}/folders", status_code=204)
async def delete_folder(
    work_id: int,
    path: str = Query(..., description="文件夹相对于作品根目录的路径"),
    db: AsyncSession = Depends(get_db),
):
    """删除文件夹（递归删除，同时删除其中的文件 DB 记录）"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    folder_rel = _normalize_path(path)
    if not folder_rel:
        raise HTTPException(status_code=400, detail="不允许删除作品根目录")

    # 查找该文件夹下所有文件的 DB 记录（兼容正斜杠和反斜杠）
    prefix_fwd = f"{work.rj_code}/{folder_rel}/"
    prefix_bwd = f"{work.rj_code}\\{folder_rel}\\"
    result = await db.execute(
        select(File).where(
            File.work_id == work_id,
            File.filepath.startswith(prefix_fwd) | File.filepath.startswith(prefix_bwd)
        )
    )
    files_in_folder = result.scalars().all()

    try:
        file_manager.delete_folder(work.rj_code, folder_rel)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 删除 DB 记录
    for f in files_in_folder:
        await db.delete(f)


@router.patch("/works/{work_id}/folders/rename")
async def rename_folder(
    work_id: int,
    data: RenameFolderRequest,
    db: AsyncSession = Depends(get_db),
):
    """重命名文件夹，同时更新其中所有文件的 DB filepath"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    old_rel = _normalize_path(data.current_path)
    if not old_rel:
        raise HTTPException(status_code=400, detail="不允许重命名作品根目录")

    try:
        new_full_path = file_manager.rename_folder(work.rj_code, old_rel, data.new_name)
        rel_to_work = _get_work_dir_relative_path(work.rj_code, new_full_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 更新文件夹下所有文件的 DB filepath（兼容正斜杠和反斜杠）
    old_prefix_fwd = f"{work.rj_code}/{old_rel}/"
    old_prefix_bwd = f"{work.rj_code}\\{old_rel}\\"
    new_prefix = f"{work.rj_code}/{rel_to_work}/" if rel_to_work else f"{work.rj_code}/"

    result = await db.execute(
        select(File).where(
            File.work_id == work_id,
            File.filepath.startswith(old_prefix_fwd) | File.filepath.startswith(old_prefix_bwd)
        )
    )
    files_in_folder = result.scalars().all()

    for f in files_in_folder:
        normalized = f.filepath.replace("\\", "/")
        if normalized.startswith(old_prefix_fwd):
            f.filepath = new_prefix + normalized[len(old_prefix_fwd):]
        else:
            f.filepath = new_prefix + normalized[len(old_prefix_bwd):]
        f.filename = os.path.basename(f.filepath)
        await db.flush()

    return {"type": "folder", "name": data.new_name, "path": rel_to_work}


# ========== 删除单个文件 ==========

@router.delete("/files/{file_id}", status_code=204)
async def delete_file(file_id: int, db: AsyncSession = Depends(get_db)):
    """删除单个文件"""
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    work = await db.get(Work, file_record.work_id)
    file_manager.delete_file(work.rj_code, file_record.filepath)
    await db.delete(file_record)


# ========== 批量删除文件 ==========

@router.post("/files/batch-delete", status_code=204)
async def batch_delete_files(data: BatchDeleteRequest, db: AsyncSession = Depends(get_db)):
    """批量删除文件"""
    result = await db.execute(select(File).where(File.id.in_(data.file_ids)))
    files = result.scalars().all()

    if not files:
        raise HTTPException(status_code=404, detail="未找到指定文件")

    # 按作品分组删除物理文件
    work_cache = {}
    for f in files:
        if f.work_id not in work_cache:
            work_cache[f.work_id] = await db.get(Work, f.work_id)
        work = work_cache[f.work_id]
        file_manager.delete_file(work.rj_code, f.filepath)
        await db.delete(f)


# ========== 重命名文件 ==========

@router.patch("/files/{file_id}/rename", response_model=FileResponse)
async def rename_file(
    file_id: int,
    data: FileRenameRequest,
    db: AsyncSession = Depends(get_db),
):
    """重命名文件"""
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    work = await db.get(Work, file_record.work_id)
    try:
        new_relative, new_name = file_manager.rename_file(
            work.rj_code, file_record.filepath, data.new_name
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="物理文件不存在")
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"文件名已存在: {data.new_name}")

    file_record.filepath = new_relative
    file_record.filename = new_name
    ext = os.path.splitext(new_name)[1]
    file_record.file_type = file_manager.get_file_type(ext)
    await db.flush()
    await db.refresh(file_record)
    return _file_to_response(file_record)


# ========== 复制文件 ==========

@router.post("/files/copy", response_model=list[FileResponse])
async def copy_files(data: FileCopyRequest, db: AsyncSession = Depends(get_db)):
    """复制文件到目标作品"""
    target_work = await db.get(Work, data.target_work_id)
    if not target_work:
        raise HTTPException(status_code=404, detail="目标作品不存在")

    result = await db.execute(select(File).where(File.id.in_(data.file_ids)))
    source_files = result.scalars().all()
    if not source_files:
        raise HTTPException(status_code=404, detail="未找到源文件")

    new_files = []
    for sf in source_files:
        source_work = await db.get(Work, sf.work_id)
        new_relative, new_name, new_size = file_manager.copy_file_to_work(
            source_work.rj_code, sf.filepath, target_work.rj_code
        )
        ext = os.path.splitext(new_name)[1]
        new_file = File(
            work_id=data.target_work_id,
            filename=new_name,
            filepath=new_relative,
            file_size=new_size,
            file_type=file_manager.get_file_type(ext),
        )
        db.add(new_file)
        await db.flush()
        await db.refresh(new_file)
        new_files.append(_file_to_response(new_file))

    return new_files


# ========== 移动文件 ==========

@router.post("/files/move", response_model=list[FileResponse])
async def move_files(data: FileCopyRequest, db: AsyncSession = Depends(get_db)):
    """移动文件到目标作品"""
    target_work = await db.get(Work, data.target_work_id)
    if not target_work:
        raise HTTPException(status_code=404, detail="目标作品不存在")

    result = await db.execute(select(File).where(File.id.in_(data.file_ids)))
    source_files = result.scalars().all()
    if not source_files:
        raise HTTPException(status_code=404, detail="未找到源文件")

    new_files = []
    for sf in source_files:
        source_work = await db.get(Work, sf.work_id)
        new_relative, new_name, new_size = file_manager.move_file_to_work(
            source_work.rj_code, sf.filepath, target_work.rj_code
        )
        ext = os.path.splitext(new_name)[1]
        new_file = File(
            work_id=data.target_work_id,
            filename=new_name,
            filepath=new_relative,
            file_size=new_size,
            file_type=file_manager.get_file_type(ext),
        )
        db.add(new_file)
        await db.delete(sf)
        await db.flush()
        await db.refresh(new_file)
        new_files.append(_file_to_response(new_file))

    return new_files


# ========== 流媒体 & 预览 ==========

@router.get("/files/{file_id}/stream")
async def stream_file(file_id: int, db: AsyncSession = Depends(get_db)):
    """流媒体播放（支持 Range 请求，用于音视频拖拽进度条）"""
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    work = await db.get(Work, file_record.work_id)
    abs_path = file_manager.get_absolute_path(work.rj_code, file_record.filepath)

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="物理文件不存在")

    file_size = abs_path.stat().st_size
    ext = file_record.file_type

    if ext not in ("audio", "video"):
        raise HTTPException(status_code=400, detail="该文件不支持流媒体播放")

    # 确定 MIME 类型
    mime_type, _ = mimetypes.guess_type(file_record.filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    # 使用 Starlette 的 FileResponse 支持 Range 请求
    return StarletteFileResponse(
        path=str(abs_path),
        media_type=mime_type,
        filename=file_record.filename,
    )


@router.get("/files/{file_id}/preview")
async def preview_file(file_id: int, db: AsyncSession = Depends(get_db)):
    """文件预览（图片/文本）"""
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    work = await db.get(Work, file_record.work_id)
    abs_path = file_manager.get_absolute_path(work.rj_code, file_record.filepath)

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="物理文件不存在")

    ext = file_record.file_type

    if ext == "image":
        mime_type, _ = mimetypes.guess_type(file_record.filename)
        return StarletteFileResponse(path=str(abs_path), media_type=mime_type or "image/png")

    elif ext == "text":
        try:
            content = abs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = abs_path.read_text(encoding="gbk")
            except Exception:
                content = "[无法解码此文件]"
        return {"filename": file_record.filename, "content": content, "type": "text"}

    else:
        raise HTTPException(status_code=400, detail="该文件类型不支持预览")
