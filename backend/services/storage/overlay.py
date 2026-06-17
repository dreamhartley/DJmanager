"""叠加存储后端：本地 + WebDAV 共存

按 rj_code 解析实际后端：
1. 本地存在该作品目录 -> 本地（同一 RJ 本地优先）
2. 否则 WebDAV 启用 -> WebDAV
3. 全新作品（两端都没有）-> 按 default_target 决定
"""

from __future__ import annotations

import os

from starlette.responses import Response

from .base import Storage, get_file_type
from .local import LocalStorage
from .webdav import WebDAVStorage


class OverlayStorage(Storage):
    name = "overlay"

    def __init__(self, local: LocalStorage, webdav: WebDAVStorage | None = None,
                 default_target: str = "webdav"):
        self.local = local
        self.webdav = webdav
        self.default_target = default_target

    async def _resolve(self, rj_code: str) -> Storage:
        if await self.local.work_exists(rj_code):
            return self.local
        if self.webdav is not None:
            if await self.webdav.work_exists(rj_code):
                return self.webdav
            return self.webdav if self.default_target == "webdav" else self.local
        return self.local

    @staticmethod
    def _rj_of(relpath: str) -> str:
        return relpath.replace("\\", "/").strip("/").split("/", 1)[0]

    # ---------- 作品级 ----------

    async def work_exists(self, rj_code: str) -> bool:
        if await self.local.work_exists(rj_code):
            return True
        return bool(self.webdav and await self.webdav.work_exists(rj_code))

    async def ensure_work_dir(self, rj_code: str) -> None:
        backend = await self._resolve(rj_code)
        await backend.ensure_work_dir(rj_code)

    async def delete_work_dir(self, rj_code: str) -> None:
        backend = await self._resolve(rj_code)
        await backend.delete_work_dir(rj_code)

    # ---------- 文件 ----------

    async def save_file(self, rj_code: str, filename: str, content: bytes, subfolder: str = "") -> tuple[str, int]:
        backend = await self._resolve(rj_code)
        return await backend.save_file(rj_code, filename, content, subfolder)

    async def save_file_from_path(self, rj_code: str, filename: str, local_path: str, subfolder: str = "") -> tuple[str, int]:
        backend = await self._resolve(rj_code)
        return await backend.save_file_from_path(rj_code, filename, local_path, subfolder)

    async def delete_file(self, rj_code: str, relpath: str) -> bool:
        backend = await self._resolve(rj_code)
        return await backend.delete_file(rj_code, relpath)

    async def rename_file(self, rj_code: str, old_relpath: str, new_name: str) -> tuple[str, str]:
        backend = await self._resolve(rj_code)
        return await backend.rename_file(rj_code, old_relpath, new_name)

    async def read_bytes(self, rj_code: str, relpath: str) -> bytes:
        backend = await self._resolve(rj_code)
        return await backend.read_bytes(rj_code, relpath)

    async def exists(self, rj_code: str, relpath: str) -> bool:
        backend = await self._resolve(rj_code)
        return await backend.exists(rj_code, relpath)

    async def stat_size(self, rj_code: str, relpath: str) -> int:
        backend = await self._resolve(rj_code)
        return await backend.stat_size(rj_code, relpath)

    async def open_stream(self, rj_code: str, relpath: str, range_header: str | None,
                          filename: str, media_type: str) -> Response:
        backend = await self._resolve(rj_code)
        return await backend.open_stream(rj_code, relpath, range_header, filename, media_type)

    # ---------- 跨作品复制/移动 ----------

    async def copy_within(self, src_relpath: str, target_rj_code: str) -> tuple[str, str, int]:
        src_backend = await self._resolve(self._rj_of(src_relpath))
        dst_backend = await self._resolve(target_rj_code)
        if src_backend is dst_backend:
            return await src_backend.copy_within(src_relpath, target_rj_code)
        return await self._bridge_copy(src_backend, dst_backend, src_relpath, target_rj_code, delete_src=False)

    async def move_within(self, src_relpath: str, target_rj_code: str) -> tuple[str, str, int]:
        src_backend = await self._resolve(self._rj_of(src_relpath))
        dst_backend = await self._resolve(target_rj_code)
        if src_backend is dst_backend:
            return await src_backend.move_within(src_relpath, target_rj_code)
        return await self._bridge_copy(src_backend, dst_backend, src_relpath, target_rj_code, delete_src=True)

    @staticmethod
    async def _bridge_copy(src_backend: Storage, dst_backend: Storage, src_relpath: str,
                           target_rj_code: str, delete_src: bool) -> tuple[str, str, int]:
        """跨后端复制/移动：读取源字节并写入目标后端"""
        src_rj = OverlayStorage._rj_of(src_relpath)
        filename = src_relpath.replace("\\", "/").rsplit("/", 1)[-1]
        content = await src_backend.read_bytes(src_rj, src_relpath)
        new_rel, size = await dst_backend.save_file(target_rj_code, filename, content)
        if delete_src:
            await src_backend.delete_file(src_rj, src_relpath)
        new_name = new_rel.rsplit("/", 1)[-1]
        return new_rel, new_name, size

    # ---------- 文件夹 ----------

    async def list_directory(self, rj_code: str, subpath: str = "") -> tuple[list[tuple[str, int]], list[str]]:
        backend = await self._resolve(rj_code)
        return await backend.list_directory(rj_code, subpath)

    async def create_folder(self, rj_code: str, subpath: str, folder_name: str) -> str:
        backend = await self._resolve(rj_code)
        return await backend.create_folder(rj_code, subpath, folder_name)

    async def delete_folder(self, rj_code: str, folder_path: str) -> None:
        backend = await self._resolve(rj_code)
        await backend.delete_folder(rj_code, folder_path)

    async def rename_folder(self, rj_code: str, folder_path: str, new_name: str) -> str:
        backend = await self._resolve(rj_code)
        return await backend.rename_folder(rj_code, folder_path, new_name)
