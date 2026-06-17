"""文件管理 API 路由"""

import os
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Query, Request
from fastapi.responses import FileResponse as StarletteFileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from database import get_db
from deps import get_storage
from models import Work, File
from schemas import (
    FileResponse, FileRenameRequest, FileCopyRequest,
    BatchDeleteRequest, FileUploadResponse,
    DirEntry, DirectoryListing,
    CreateFolderRequest, RenameFolderRequest,
)
from services.storage import OverlayStorage, get_file_type

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
    storage: OverlayStorage = Depends(get_storage),
):
    """获取目录内容（文件 + 文件夹）"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    # 规范化 path（统一正斜杠，去除首尾/）
    subpath = _normalize_path(path)

    # 获取目录中的文件和文件夹（新签名：files=[(relpath,size)], folders=[relpath]）
    files_with_size, folder_paths = await storage.list_directory(work.rj_code, subpath)

    # 查找文件对应的 DB 记录
    # 构建反斜杠版本用于匹配旧 DB 记录（Windows 历史数据）
    file_paths = [fp for fp, _ in files_with_size]
    size_map = dict(files_with_size)
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
                file_size=size_map.get(fp, 0),
                file_type=get_file_type(os.path.splitext(fp)[1]),
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
    storage: OverlayStorage = Depends(get_storage),
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
            relative_path, file_size = await storage.save_file(
                work.rj_code, upload_file.filename, content, subfolder
            )
            ext = os.path.splitext(upload_file.filename)[1]
            file_type = get_file_type(ext)

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
    storage: OverlayStorage = Depends(get_storage),
):
    """创建文件夹"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    subpath = _normalize_path(path)
    try:
        folder_rel_path = await storage.create_folder(work.rj_code, subpath, data.folder_name)
        rel_to_work = _get_work_dir_relative_path(work.rj_code, folder_rel_path)
        return {"type": "folder", "name": data.folder_name, "path": rel_to_work}
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/works/{work_id}/folders", status_code=204)
async def delete_folder(
    work_id: int,
    path: str = Query(..., description="文件夹相对于作品根目录的路径"),
    db: AsyncSession = Depends(get_db),
    storage: OverlayStorage = Depends(get_storage),
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
        await storage.delete_folder(work.rj_code, folder_rel)
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
    storage: OverlayStorage = Depends(get_storage),
):
    """重命名文件夹，同时更新其中所有文件的 DB filepath"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    old_rel = _normalize_path(data.current_path)
    if not old_rel:
        raise HTTPException(status_code=400, detail="不允许重命名作品根目录")

    try:
        new_full_path = await storage.rename_folder(work.rj_code, old_rel, data.new_name)
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
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    storage: OverlayStorage = Depends(get_storage),
):
    """删除单个文件"""
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    work = await db.get(Work, file_record.work_id)
    await storage.delete_file(work.rj_code, file_record.filepath)
    await db.delete(file_record)


# ========== 批量删除文件 ==========

@router.post("/files/batch-delete", status_code=204)
async def batch_delete_files(
    data: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    storage: OverlayStorage = Depends(get_storage),
):
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
        await storage.delete_file(work.rj_code, f.filepath)
        await db.delete(f)


# ========== 重命名文件 ==========

@router.patch("/files/{file_id}/rename", response_model=FileResponse)
async def rename_file(
    file_id: int,
    data: FileRenameRequest,
    db: AsyncSession = Depends(get_db),
    storage: OverlayStorage = Depends(get_storage),
):
    """重命名文件"""
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    work = await db.get(Work, file_record.work_id)
    try:
        new_relative, new_name = await storage.rename_file(
            work.rj_code, file_record.filepath, data.new_name
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="物理文件不存在")
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"文件名已存在: {data.new_name}")

    file_record.filepath = new_relative
    file_record.filename = new_name
    ext = os.path.splitext(new_name)[1]
    file_record.file_type = get_file_type(ext)
    await db.flush()
    await db.refresh(file_record)
    return _file_to_response(file_record)


# ========== 复制文件 ==========

@router.post("/files/copy", response_model=list[FileResponse])
async def copy_files(
    data: FileCopyRequest,
    db: AsyncSession = Depends(get_db),
    storage: OverlayStorage = Depends(get_storage),
):
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
        new_relative, new_name, new_size = await storage.copy_within(
            sf.filepath, target_work.rj_code
        )
        ext = os.path.splitext(new_name)[1]
        new_file = File(
            work_id=data.target_work_id,
            filename=new_name,
            filepath=new_relative,
            file_size=new_size,
            file_type=get_file_type(ext),
        )
        db.add(new_file)
        await db.flush()
        await db.refresh(new_file)
        new_files.append(_file_to_response(new_file))

    return new_files


# ========== 移动文件 ==========

@router.post("/files/move", response_model=list[FileResponse])
async def move_files(
    data: FileCopyRequest,
    db: AsyncSession = Depends(get_db),
    storage: OverlayStorage = Depends(get_storage),
):
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
        new_relative, new_name, new_size = await storage.move_within(
            sf.filepath, target_work.rj_code
        )
        ext = os.path.splitext(new_name)[1]
        new_file = File(
            work_id=data.target_work_id,
            filename=new_name,
            filepath=new_relative,
            file_size=new_size,
            file_type=get_file_type(ext),
        )
        db.add(new_file)
        await db.delete(sf)
        await db.flush()
        await db.refresh(new_file)
        new_files.append(_file_to_response(new_file))

    return new_files


# ========== 流媒体 & 预览 ==========

@router.get("/files/{file_id}/stream")
async def stream_file(
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    storage: OverlayStorage = Depends(get_storage),
):
    """流媒体播放（支持 Range 请求，用于音视频拖拽进度条）"""
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    work = await db.get(Work, file_record.work_id)

    if not await storage.exists(work.rj_code, file_record.filepath):
        raise HTTPException(status_code=404, detail="物理文件不存在")

    file_type = file_record.file_type
    if file_type not in ("audio", "video"):
        raise HTTPException(status_code=400, detail="该文件不支持流媒体播放")

    # 确定 MIME 类型
    mime_type, _ = mimetypes.guess_type(file_record.filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    range_header = request.headers.get("range")
    return await storage.open_stream(
        work.rj_code, file_record.filepath, range_header,
        file_record.filename, mime_type,
    )


@router.get("/files/{file_id}/preview")
async def preview_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    storage: OverlayStorage = Depends(get_storage),
):
    """文件预览（图片/pdf/文本）"""
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    work = await db.get(Work, file_record.work_id)

    if not await storage.exists(work.rj_code, file_record.filepath):
        raise HTTPException(status_code=404, detail="物理文件不存在")

    file_type = file_record.file_type

    if file_type in ("image", "pdf"):
        mime_type, _ = mimetypes.guess_type(file_record.filename)
        if file_type == "pdf":
            mime_type = mime_type or "application/pdf"
        else:
            mime_type = mime_type or "image/png"
        return await storage.open_stream(
            work.rj_code, file_record.filepath, None,
            file_record.filename, mime_type,
        )

    elif file_type == "text":
        try:
            raw_data = await storage.read_bytes(work.rj_code, file_record.filepath)
            # 尝试常见编码进行解码：UTF-8 (带/不带BOM), CP932 (日文Windows), GB18030 (中文Windows), UTF-16, EUC-JP
            encodings = ["utf-8-sig", "cp932", "gb18030", "utf-16", "euc_jp"]
            content = None
            for enc in encodings:
                try:
                    content = raw_data.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if content is None:
                content = raw_data.decode("utf-8", errors="replace")
        except Exception as e:
            content = f"[无法解码此文件]: {str(e)}"
        return {"filename": file_record.filename, "content": content, "type": "text"}

    else:
        raise HTTPException(status_code=400, detail="该文件类型不支持预览")
