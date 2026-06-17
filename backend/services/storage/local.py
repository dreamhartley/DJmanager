"""本地文件系统存储后端"""

from __future__ import annotations

import os
import shutil
import mimetypes
from pathlib import Path

from starlette.responses import FileResponse as StarletteFileResponse, Response

from config import WORKS_DIR
from .base import Storage


class LocalStorage(Storage):
    """基于本地文件系统的存储后端（根目录为 data/works）"""

    name = "local"

    def __init__(self, root: Path = WORKS_DIR):
        self.root = Path(root)

    # ---------- 内部工具 ----------

    def _abs(self, relpath: str) -> Path:
        return self.root / relpath.replace("\\", "/")

    @staticmethod
    def _unique_target(target_dir: Path, filename: str) -> Path:
        base, ext = os.path.splitext(filename)
        target_path = target_dir / filename
        counter = 1
        while target_path.exists():
            target_path = target_dir / f"{base}_{counter}{ext}"
            counter += 1
        return target_path

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    # ---------- 作品级 ----------

    async def work_exists(self, rj_code: str) -> bool:
        return (self.root / rj_code).is_dir()

    async def ensure_work_dir(self, rj_code: str) -> None:
        (self.root / rj_code).mkdir(parents=True, exist_ok=True)

    async def delete_work_dir(self, rj_code: str) -> None:
        work_dir = self.root / rj_code
        if work_dir.exists():
            shutil.rmtree(work_dir)

    # ---------- 文件 ----------

    async def save_file(self, rj_code: str, filename: str, content: bytes, subfolder: str = "") -> tuple[str, int]:
        target_dir = self.root / rj_code / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._unique_target(target_dir, filename)
        target_path.write_bytes(content)
        return self._relative(target_path), target_path.stat().st_size

    async def save_file_from_path(self, rj_code: str, filename: str, local_path: str, subfolder: str = "") -> tuple[str, int]:
        target_dir = self.root / rj_code / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._unique_target(target_dir, filename)
        shutil.move(str(local_path), str(target_path))
        return self._relative(target_path), target_path.stat().st_size

    async def delete_file(self, rj_code: str, relpath: str) -> bool:
        abs_path = self._abs(relpath)
        if abs_path.exists() and abs_path.is_file():
            abs_path.unlink()
            return True
        return False

    async def rename_file(self, rj_code: str, old_relpath: str, new_name: str) -> tuple[str, str]:
        old_path = self._abs(old_relpath)
        if not old_path.exists():
            raise FileNotFoundError(f"文件不存在: {old_relpath}")
        new_path = old_path.parent / new_name
        if new_path.exists():
            raise FileExistsError(f"目标文件已存在: {new_name}")
        old_path.rename(new_path)
        return self._relative(new_path), new_name

    async def read_bytes(self, rj_code: str, relpath: str) -> bytes:
        return self._abs(relpath).read_bytes()

    async def exists(self, rj_code: str, relpath: str) -> bool:
        return self._abs(relpath).exists()

    async def stat_size(self, rj_code: str, relpath: str) -> int:
        return self._abs(relpath).stat().st_size

    async def open_stream(self, rj_code: str, relpath: str, range_header: str | None,
                          filename: str, media_type: str) -> Response:
        abs_path = self._abs(relpath)
        if not abs_path.exists():
            raise FileNotFoundError(f"物理文件不存在: {relpath}")
        # Starlette FileResponse 原生支持 Range 请求
        return StarletteFileResponse(path=str(abs_path), media_type=media_type, filename=filename)

    # ---------- 跨作品复制/移动 ----------

    async def copy_within(self, src_relpath: str, target_rj_code: str) -> tuple[str, str, int]:
        src_path = self._abs(src_relpath)
        if not src_path.exists():
            raise FileNotFoundError(f"源文件不存在: {src_relpath}")
        target_dir = self.root / target_rj_code
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._unique_target(target_dir, src_path.name)
        shutil.copy2(src_path, target_path)
        return self._relative(target_path), target_path.name, target_path.stat().st_size

    async def move_within(self, src_relpath: str, target_rj_code: str) -> tuple[str, str, int]:
        src_path = self._abs(src_relpath)
        if not src_path.exists():
            raise FileNotFoundError(f"源文件不存在: {src_relpath}")
        target_dir = self.root / target_rj_code
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._unique_target(target_dir, src_path.name)
        shutil.move(str(src_path), str(target_path))
        return self._relative(target_path), target_path.name, target_path.stat().st_size

    # ---------- 文件夹 ----------

    async def list_directory(self, rj_code: str, subpath: str = "") -> tuple[list[tuple[str, int]], list[str]]:
        target_dir = self.root / rj_code / subpath
        if not target_dir.exists():
            return [], []
        files: list[tuple[str, int]] = []
        folders: list[str] = []
        for entry in sorted(target_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            rel = self._relative(entry)
            if entry.is_dir():
                folders.append(rel)
            elif entry.is_file():
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                files.append((rel, size))
        return files, folders

    async def create_folder(self, rj_code: str, subpath: str, folder_name: str) -> str:
        target_dir = self.root / rj_code / subpath
        new_folder = target_dir / folder_name
        if new_folder.exists():
            raise FileExistsError(f"文件夹已存在: {folder_name}")
        new_folder.mkdir(parents=True)
        return self._relative(new_folder)

    async def delete_folder(self, rj_code: str, folder_path: str) -> None:
        target = self.root / rj_code / folder_path
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")
        if str(target.resolve()) == str((self.root / rj_code).resolve()):
            raise ValueError("不允许删除作品根目录")
        shutil.rmtree(target)

    async def rename_folder(self, rj_code: str, folder_path: str, new_name: str) -> str:
        target = self.root / rj_code / folder_path
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")
        new_path = target.parent / new_name
        if new_path.exists():
            raise FileExistsError(f"目标已存在: {new_name}")
        target.rename(new_path)
        return self._relative(new_path)
