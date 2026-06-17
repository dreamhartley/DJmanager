"""扫描注册服务：将存储中存在的物理文件注册到数据库。

用途：
1. 添加作品时自动扫描用户预先放置的 RJ 文件夹（孤儿文件注册）。
2. 作品详情页"重新扫描"按钮。
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Work, File
from services.storage import OverlayStorage
from services.storage.manager import walk_work_files


async def register_orphan_files(
    db: AsyncSession,
    storage: OverlayStorage,
    work: Work,
) -> int:
    """扫描作品目录，将未注册到 DB 的文件补登记。

    返回新增的文件数量。filepath 统一存为正斜杠、含 rj_code 前缀。
    """
    rj_code = work.rj_code

    # 仅当作品目录存在时才扫描
    if not await storage.work_exists(rj_code):
        return 0

    # 取磁盘上全部文件（含 rj_code 前缀、正斜杠）
    disk_files = await walk_work_files(storage, rj_code)
    disk_paths = {fp for fp, _ in disk_files}
    size_map = {fp: size for fp, size in disk_files}

    # 取 DB 已有记录（兼容历史反斜杠路径，统一成正斜杠比对）
    result = await db.execute(select(File).where(File.work_id == work.id))
    existing = result.scalars().all()
    existing_normalized = {f.filepath.replace("\\", "/") for f in existing}

    new_count = 0
    for relpath, size in disk_files:
        if relpath in existing_normalized:
            continue
        filename = os.path.basename(relpath)
        ext = os.path.splitext(filename)[1]
        from services.storage import get_file_type
        db.add(File(
            work_id=work.id,
            filename=filename,
            filepath=relpath,
            file_size=size_map.get(relpath, 0),
            file_type=get_file_type(ext),
        ))
        new_count += 1

    if new_count:
        await db.flush()
    return new_count
