"""存储单例管理

- 从数据库 settings 表读取 WebDAV 配置，构建 OverlayStorage 单例。
- 配置变更后调用 rebuild() 即时生效（关闭旧 WebDAV client，重建实例）。
- 提供 walk_work_files 辅助：递归遍历某作品下的全部文件，供扫描注册使用。

配置键（均在 settings 表中）：
- webdav_enabled   : "true"/"false"
- webdav_url       : WebDAV 服务地址（如 https://dav.example.com）
- webdav_username  : 用户名
- webdav_password  : 密码   # TODO: 加密存储密码（当前自托管场景明文）
- webdav_base_path : 对应 data/works 的作品根目录（相对 WebDAV 根）
- default_target   : 新作品默认落点 "local" / "webdav"
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import WORKS_DIR
from database import async_session
from models import Setting
from .local import LocalStorage
from .webdav import WebDAVStorage
from .overlay import OverlayStorage

# settings 表中与存储相关的所有键
STORAGE_KEYS = (
    "webdav_enabled",
    "webdav_url",
    "webdav_username",
    "webdav_password",
    "webdav_base_path",
    "default_target",
)

DEFAULTS = {
    "webdav_enabled": "false",
    "webdav_url": "",
    "webdav_username": "",
    "webdav_password": "",
    "webdav_base_path": "",
    "default_target": "webdav",
}


class StorageManager:
    """OverlayStorage 单例持有者"""

    def __init__(self) -> None:
        self._overlay: OverlayStorage | None = None

    def get(self) -> OverlayStorage:
        if self._overlay is None:
            # 未初始化时回退到纯本地（避免启动早期报错）
            self._overlay = OverlayStorage(local=LocalStorage(WORKS_DIR), webdav=None)
        return self._overlay

    async def init(self) -> None:
        """应用启动时从 DB 加载配置并构建单例"""
        await self.rebuild()

    async def rebuild(self) -> None:
        """重新读取配置并重建 OverlayStorage（关闭旧 WebDAV client）"""
        async with async_session() as db:
            cfg = await _load_settings(db)

        old = self._overlay
        webdav: WebDAVStorage | None = None
        if cfg["webdav_enabled"].lower() == "true" and cfg["webdav_url"]:
            webdav = WebDAVStorage(
                url=cfg["webdav_url"],
                username=cfg["webdav_username"],
                password=cfg["webdav_password"],
                base_path=cfg["webdav_base_path"],
            )
        default_target = cfg["default_target"] or "webdav"
        self._overlay = OverlayStorage(
            local=LocalStorage(WORKS_DIR),
            webdav=webdav,
            default_target=default_target,
        )

        # 关闭旧 client（若有 WebDAV）
        if old is not None and old.webdav is not None and old.webdav is not webdav:
            await old.webdav.aclose()

    async def aclose(self) -> None:
        """应用关闭时释放资源"""
        if self._overlay is not None and self._overlay.webdav is not None:
            await self._overlay.webdav.aclose()
        self._overlay = None


storage_manager = StorageManager()


async def _load_settings(db: AsyncSession) -> dict[str, str]:
    """从 DB 读取存储相关配置，缺失项用默认值填充"""
    result = await db.execute(select(Setting).where(Setting.key.in_(STORAGE_KEYS)))
    rows = {r.key: r.value for r in result.scalars().all()}
    cfg = {k: rows.get(k, DEFAULTS.get(k, "")) for k in STORAGE_KEYS}
    return cfg


async def load_storage_settings(db: AsyncSession) -> dict[str, str]:
    """供 settings router 使用的公开读取函数"""
    return await _load_settings(db)


async def save_storage_settings(db: AsyncSession, updates: dict[str, str]) -> dict[str, str]:
    """将 updates 合并写入 settings 表（仅限 STORAGE_KEYS 中的键）。

    注意：密码值为空字符串或 "***" 时视为"保持原值不变"，避免前端回显掩码覆盖真实密码。
    """
    for key in STORAGE_KEYS:
        if key not in updates:
            continue
        value = updates[key]
        # 掩码保护：前端回显密码为空或 *** 时不覆盖
        if key == "webdav_password" and value in ("", "***"):
            continue
        result = await db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting is None:
            setting = Setting(key=key, value=value)
            db.add(setting)
        else:
            setting.value = value
    await db.flush()
    return await _load_settings(db)


async def walk_work_files(storage: OverlayStorage, rj_code: str) -> list[tuple[str, int]]:
    """递归遍历某作品的全部文件。

    返回 [(relpath, size), ...]，relpath 含 rj_code 前缀、正斜杠。
    用于"扫描注册孤儿文件"。
    """
    result: list[tuple[str, int]] = []

    async def _walk(rel_dir: str) -> None:
        files, folders = await storage.list_directory(rj_code, rel_dir)
        result.extend(files)
        for folder_rel in folders:
            # folder_rel 含 rj_code 前缀，需转回相对作品根的 subpath
            sub = folder_rel
            prefix = f"{rj_code}/"
            if sub.startswith(prefix):
                sub = sub[len(prefix):]
            await _walk(sub)

    if await storage.work_exists(rj_code):
        await _walk("")
    return result
