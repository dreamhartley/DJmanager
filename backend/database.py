"""数据库引擎与会话管理"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """初始化数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 迁移：将已有以 .pdf 结尾的 file_type 为 other 的记录更新为 pdf
    async with async_session() as session:
        from sqlalchemy import update
        from models import File
        await session.execute(
            update(File)
            .where(File.filename.ilike("%.pdf"), File.file_type == "other")
            .values(file_type="pdf")
        )
        await session.commit()
