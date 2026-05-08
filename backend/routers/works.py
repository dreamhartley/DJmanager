"""作品管理 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Work, File
from schemas import WorkCreate, WorkResponse, WorkListResponse
from services.scraper import scraper_service
from services.file_manager import file_manager

router = APIRouter(prefix="/api/works", tags=["作品管理"])


@router.post("", response_model=WorkResponse, status_code=201)
async def add_work(data: WorkCreate, db: AsyncSession = Depends(get_db)):
    """添加作品：通过 RJ 编号刮削 DLsite 信息"""
    rj_code = data.rj_code.strip().upper()
    if not rj_code.startswith("RJ"):
        rj_code = "RJ" + rj_code

    # 检查是否已存在
    existing = await db.execute(select(Work).where(Work.rj_code == rj_code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"作品 {rj_code} 已存在")

    # 刮削作品信息
    try:
        info = await scraper_service.fetch_work(rj_code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"刮削失败: {e}")

    # 下载封面
    cover_path = ""
    if info["cover_url"]:
        cover_path = await scraper_service.download_cover(info["cover_url"], rj_code)

    # 创建作品记录
    import json
    work = Work(
        rj_code=info["rj_code"],
        title=info["title"],
        circle=info["circle"],
        voice_actors=json.dumps(info["voice_actors"], ensure_ascii=False),
        release_date=info["release_date"],
        genres=json.dumps(info["genres"], ensure_ascii=False),
        cover_url=info["cover_url"],
        cover_path=cover_path,
        description=info["description"],
        series=info["series"],
        age_category=info["age_category"],
    )
    db.add(work)
    await db.flush()

    # 重新查询以加载关联的 files（避免 MissingGreenlet 错误）
    result = await db.execute(
        select(Work).where(Work.id == work.id).options(selectinload(Work.files))
    )
    work = result.scalar_one()

    return _work_to_response(work)


@router.get("", response_model=list[WorkListResponse])
async def list_works(db: AsyncSession = Depends(get_db)):
    """获取所有作品列表"""
    result = await db.execute(
        select(Work).options(selectinload(Work.files)).order_by(Work.created_at.desc())
    )
    works = result.scalars().all()

    return [
        WorkListResponse(
            id=w.id,
            rj_code=w.rj_code,
            title=w.title,
            circle=w.circle,
            cover_path=w.cover_path,
            genres=w.get_genres(),
            voice_actors=w.get_voice_actors(),
            file_count=len(w.files),
            created_at=w.created_at,
        )
        for w in works
    ]


@router.get("/{rj_code}", response_model=WorkResponse)
async def get_work(rj_code: str, db: AsyncSession = Depends(get_db)):
    """获取单个作品详情（通过 RJ 编号，如 RJ378563）"""
    # 规范化 RJ 编号
    rj_code = rj_code.strip().upper()
    if not rj_code.startswith("RJ"):
        rj_code = "RJ" + rj_code

    result = await db.execute(
        select(Work).where(Work.rj_code == rj_code).options(selectinload(Work.files))
    )
    work = result.scalar_one_or_none()
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")
    return _work_to_response(work)


@router.delete("/{work_id}", status_code=204)
async def delete_work(work_id: int, db: AsyncSession = Depends(get_db)):
    """删除作品及其所有文件"""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")

    # 删除文件目录
    file_manager.delete_work_dir(work.rj_code)

    # 删除数据库记录（级联删除 files）
    await db.delete(work)


def _work_to_response(work: Work) -> WorkResponse:
    return WorkResponse(
        id=work.id,
        rj_code=work.rj_code,
        title=work.title,
        circle=work.circle,
        voice_actors=work.get_voice_actors(),
        release_date=work.release_date,
        genres=work.get_genres(),
        cover_url=work.cover_url,
        cover_path=work.cover_path,
        description=work.description,
        series=work.series,
        age_category=work.age_category,
        file_count=len(work.files),
        created_at=work.created_at,
        updated_at=work.updated_at,
    )
