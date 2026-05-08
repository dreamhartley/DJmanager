"""DLsite 刮削服务 - 基于 dlsite-async 库"""

import json
import os
import re
from pathlib import Path

import httpx
from dlsite_async import DlsiteAPI

from config import COVERS_DIR


class ScraperService:
    """DLsite 作品信息刮削器"""

    def __init__(self):
        self._api: DlsiteAPI | None = None

    async def _get_api(self) -> DlsiteAPI:
        if self._api is None:
            self._api = DlsiteAPI()
        return self._api

    @staticmethod
    def _normalize_rj_code(rj_code: str) -> str:
        """标准化 RJ 编号：确保大写并补全格式"""
        code = rj_code.strip().upper()
        # 如果只有数字部分，补全 RJ 前缀
        if not code.startswith("RJ"):
            code = "RJ" + code
        return code

    async def fetch_work(self, rj_code: str) -> dict:
        """根据 RJ 编号获取作品信息"""
        api = await self._get_api()
        normalized = self._normalize_rj_code(rj_code)

        try:
            work = await api.get_work(normalized)
        except Exception as e:
            raise ValueError(f"获取作品信息失败 (RJ: {normalized}): {e}")

        if work is None:
            raise ValueError(f"未找到作品: {normalized}")

        # 提取数据 - 使用 dlsite-async Work 类的实际属性名
        voice_actors = getattr(work, "voice_actor", None) or []
        voice_actors = [str(v) for v in voice_actors]

        genres = getattr(work, "genre", None) or []
        genres = [str(g) for g in genres]

        # age_category 是 AgeCategory 枚举，转为整数
        age_category = getattr(work, "age_category", None)
        if age_category is not None:
            try:
                age_category = int(age_category.value)
            except (AttributeError, TypeError):
                age_category = int(age_category) if age_category else 0
        else:
            age_category = 0

        # release_date 可能是 datetime 对象
        release_date = getattr(work, "release_date", None)
        if release_date is not None:
            if hasattr(release_date, "strftime"):
                release_date = release_date.strftime("%Y-%m-%d")
            else:
                release_date = str(release_date)
        else:
            release_date = ""

        cover_url = getattr(work, "work_image", "") or ""
        # 补全协议前缀（DLsite 可能返回 // 开头的协议相对 URL）
        if cover_url.startswith("//"):
            cover_url = "https:" + cover_url
        elif cover_url and not cover_url.startswith("http://") and not cover_url.startswith("https://"):
            cover_url = "https://" + cover_url.lstrip("/")

        result = {
            "rj_code": normalized,
            "title": getattr(work, "work_name", "") or "",
            "circle": getattr(work, "circle", "") or "",
            "voice_actors": voice_actors,
            "release_date": release_date,
            "genres": genres,
            "cover_url": cover_url,
            "description": getattr(work, "description", "") or "",
            "series": getattr(work, "series", "") or "",
            "age_category": age_category,
        }
        return result

    async def download_cover(self, cover_url: str, rj_code: str) -> str:
        """下载封面图片，返回本地相对路径"""
        if not cover_url:
            return ""

        # 从 URL 提取扩展名
        ext = os.path.splitext(cover_url.split("?")[0])[1]
        if not ext or len(ext) > 5:
            ext = ".jpg"

        filename = f"{rj_code}{ext}"
        filepath = COVERS_DIR / filename

        # 如果已存在则跳过下载
        if filepath.exists():
            return f"covers/{filename}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.dlsite.com/",
            }
            try:
                response = await client.get(cover_url, headers=headers)
                response.raise_for_status()
                filepath.write_bytes(response.content)
                return f"covers/{filename}"
            except Exception as e:
                print(f"封面下载失败 ({rj_code}): {e}")
                return ""


# 单例
scraper_service = ScraperService()
