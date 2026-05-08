"""分块上传 API 路由 - 用于 Cloudflare 代理环境下的大文件上传"""

import os
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import WORKS_DIR, DATA_DIR
from database import get_db
from models import Work, File
from schemas import FileResponse, FileUploadResponse
from services.file_manager import file_manager

router = APIRouter(prefix="/api", tags=["分块上传"])

# 分块上传临时目录
CHUNKS_DIR = DATA_DIR / "chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)


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
    return p.replace("\\", "/").strip("/")


# ========== Cloudflare 检测 ==========

@router.get("/upload/check-cf")
async def check_cloudflare(request: Request):
    """检测请求是否经过 Cloudflare 代理，返回是否需要分块上传"""
    # Cloudflare 特征 header
    cf_headers = [
        "cf-ray",
        "cf-connecting-ip",
        "cf-ipcountry",
        "cf-visitor",
    ]
    is_cf = any(h in request.headers for h in cf_headers)
    return {
        "is_cloudflare": is_cf,
        "chunk_size": 80 * 1024 * 1024,       # 80MB
        "chunk_threshold": 100 * 1024 * 1024,  # 100MB - 超过此大小触发分块
    }


# ========== 初始化分块上传 ==========

@router.post("/upload/init")
async def init_chunked_upload(
    request: Request,
    work_id: int = Query(..., description="作品 ID"),
    filename: str = Query(..., description="原始文件名"),
    total_size: int = Query(..., description="文件总大小（字节）"),
    total_chunks: int = Query(..., description="总分块数"),
    path: str = Query(default="", description="目标子目录"),
    db: AsyncSession = Depends(get_db),
):
    """初始化分块上传会话，返回 upload_id"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    upload_id = str(uuid.uuid4())

    # 创建临时目录存放分块
    chunk_dir = CHUNKS_DIR / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)

    # 写入元数据文件
    meta_path = chunk_dir / "_meta.txt"
    meta_path.write_text(
        f"work_id={work_id}\n"
        f"rj_code={work.rj_code}\n"
        f"filename={filename}\n"
        f"total_size={total_size}\n"
        f"total_chunks={total_chunks}\n"
        f"path={_normalize_path(path)}\n",
        encoding="utf-8",
    )

    return {
        "upload_id": upload_id,
        "total_chunks": total_chunks,
    }


# ========== 上传单个分块 ==========

@router.post("/upload/chunk")
async def upload_chunk(
    upload_id: str = Query(..., description="上传会话 ID"),
    chunk_index: int = Query(..., description="分块索引（从0开始）"),
    chunk: UploadFile = FastAPIFile(...),
):
    """上传单个分块"""
    chunk_dir = CHUNKS_DIR / upload_id
    if not chunk_dir.exists():
        raise HTTPException(status_code=404, detail="上传会话不存在或已过期")

    # 保存分块
    chunk_path = chunk_dir / f"chunk_{chunk_index:05d}"
    content = await chunk.read()
    chunk_path.write_bytes(content)

    return {"chunk_index": chunk_index, "size": len(content)}


# ========== 合并分块 ==========

@router.post("/upload/complete", response_model=FileUploadResponse)
async def complete_chunked_upload(
    upload_id: str = Query(..., description="上传会话 ID"),
    db: AsyncSession = Depends(get_db),
):
    """合并所有分块为完整文件"""
    chunk_dir = CHUNKS_DIR / upload_id
    if not chunk_dir.exists():
        raise HTTPException(status_code=404, detail="上传会话不存在或已过期")

    # 读取元数据
    meta_path = chunk_dir / "_meta.txt"
    if not meta_path.exists():
        raise HTTPException(status_code=400, detail="上传元数据丢失")

    meta = {}
    for line in meta_path.read_text(encoding="utf-8").strip().split("\n"):
        key, value = line.split("=", 1)
        meta[key] = value

    work_id = int(meta["work_id"])
    rj_code = meta["rj_code"]
    filename = meta["filename"]
    total_chunks = int(meta["total_chunks"])
    subfolder = meta.get("path", "")

    # 验证作品是否存在
    work = await db.get(Work, work_id)
    if not work:
        _cleanup_chunks(chunk_dir)
        raise HTTPException(status_code=404, detail="作品不存在")

    # 验证所有分块是否已上传
    chunk_files = sorted(
        [f for f in chunk_dir.iterdir() if f.name.startswith("chunk_")],
        key=lambda f: f.name,
    )
    if len(chunk_files) != total_chunks:
        raise HTTPException(
            status_code=400,
            detail=f"分块不完整：期望 {total_chunks} 个，实际 {len(chunk_files)} 个",
        )

    # 合并分块到目标路径
    target_dir = WORKS_DIR / rj_code / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    # 处理重名
    base, ext = os.path.splitext(filename)
    target_path = target_dir / filename
    counter = 1
    while target_path.exists():
        target_path = target_dir / f"{base}_{counter}{ext}"
        counter += 1

    uploaded = []
    errors = []

    try:
        # 顺序写入所有分块
        with open(target_path, "wb") as f:
            for chunk_file in chunk_files:
                f.write(chunk_file.read_bytes())

        file_size = target_path.stat().st_size
        relative_path = target_path.relative_to(WORKS_DIR).as_posix()
        file_type = file_manager.get_file_type(ext)

        # 创建数据库记录
        file_record = File(
            work_id=work_id,
            filename=target_path.name,
            filepath=relative_path,
            file_size=file_size,
            file_type=file_type,
        )
        db.add(file_record)
        await db.flush()
        await db.refresh(file_record)
        uploaded.append(_file_to_response(file_record))

    except Exception as e:
        errors.append(f"{filename}: {e}")
        # 如果合并失败，清理已创建的目标文件
        if target_path.exists():
            target_path.unlink()
    finally:
        # 清理分块临时文件
        _cleanup_chunks(chunk_dir)

    return FileUploadResponse(files=uploaded, errors=errors)


# ========== 取消/清理 ==========

@router.delete("/upload/{upload_id}")
async def cancel_chunked_upload(upload_id: str):
    """取消分块上传，清理临时文件"""
    chunk_dir = CHUNKS_DIR / upload_id
    if chunk_dir.exists():
        _cleanup_chunks(chunk_dir)
    return {"status": "cancelled"}


def _cleanup_chunks(chunk_dir: Path):
    """清理分块临时目录"""
    try:
        shutil.rmtree(chunk_dir)
    except Exception:
        pass
