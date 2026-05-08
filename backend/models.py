"""SQLAlchemy ORM 模型定义"""

import json
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Work(Base):
    """作品模型"""
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rj_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    circle: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    voice_actors: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON 数组
    release_date: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    genres: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON 数组
    cover_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    cover_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    series: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    age_category: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    files: Mapped[list["File"]] = relationship("File", back_populates="work", cascade="all, delete-orphan")

    def get_voice_actors(self) -> list[str]:
        return json.loads(self.voice_actors) if self.voice_actors else []

    def get_genres(self) -> list[str]:
        return json.loads(self.genres) if self.genres else []


class File(Base):
    """文件模型"""
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(Integer, ForeignKey("works.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    filepath: Mapped[str] = mapped_column(String(1000), nullable=False)  # 相对于作品目录的路径
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    work: Mapped["Work"] = relationship("Work", back_populates="files")
