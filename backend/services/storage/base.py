"""存储后端抽象基类

所有存储后端（本地 / WebDAV）实现统一的异步接口。
约定：
- `rj_code` 为作品编号，作品根目录即 `<root>/<rj_code>`。
- `relpath` 为相对于存储根目录（即 `data/works` 对应的位置）的路径，使用正斜杠，且包含 `rj_code` 前缀，例如 `RJ123/sub/a.mp3`。
- `subpath` / `folder_path` 为相对于作品根目录的路径（不含 `rj_code` 前缀）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from starlette.responses import Response

from config import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TEXT_EXTENSIONS,
    PDF_EXTENSIONS,
)


def get_file_type(ext: str) -> str:
    """根据扩展名判断文件类型（后端无关）"""
    ext = ext.lower()
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    elif ext in VIDEO_EXTENSIONS:
        return "video"
    elif ext in IMAGE_EXTENSIONS:
        return "image"
    elif ext in TEXT_EXTENSIONS:
        return "text"
    elif ext in PDF_EXTENSIONS:
        return "pdf"
    else:
        return "other"


class Storage(ABC):
    """存储后端统一接口"""

    name: str = "base"

    # ---------- 作品级 ----------

    @abstractmethod
    async def work_exists(self, rj_code: str) -> bool:
        """作品根目录是否存在"""

    @abstractmethod
    async def ensure_work_dir(self, rj_code: str) -> None:
        """确保作品根目录存在"""

    @abstractmethod
    async def delete_work_dir(self, rj_code: str) -> None:
        """删除作品根目录及其全部文件（不含封面，封面由本地统一管理）"""

    # ---------- 文件 ----------

    @abstractmethod
    async def save_file(self, rj_code: str, filename: str, content: bytes, subfolder: str = "") -> tuple[str, int]:
        """保存文件，返回 (relpath, size)；自动处理重名"""

    @abstractmethod
    async def save_file_from_path(self, rj_code: str, filename: str, local_path: str, subfolder: str = "") -> tuple[str, int]:
        """从本地临时文件保存（用于分块上传合并），返回 (relpath, size)；自动处理重名"""

    @abstractmethod
    async def delete_file(self, rj_code: str, relpath: str) -> bool:
        """删除文件"""

    @abstractmethod
    async def rename_file(self, rj_code: str, old_relpath: str, new_name: str) -> tuple[str, str]:
        """同目录重命名文件，返回 (new_relpath, new_name)"""

    @abstractmethod
    async def read_bytes(self, rj_code: str, relpath: str) -> bytes:
        """读取文件全部字节（用于文本预览等小文件）"""

    @abstractmethod
    async def exists(self, rj_code: str, relpath: str) -> bool:
        """文件/目录是否存在"""

    @abstractmethod
    async def stat_size(self, rj_code: str, relpath: str) -> int:
        """获取文件大小"""

    @abstractmethod
    async def open_stream(self, rj_code: str, relpath: str, range_header: str | None,
                          filename: str, media_type: str) -> Response:
        """返回可流式播放/下载的响应（本地走 FileResponse，WebDAV 走 Range 转发）"""

    # ---------- 跨作品复制/移动（同后端内）----------

    @abstractmethod
    async def copy_within(self, src_relpath: str, target_rj_code: str) -> tuple[str, str, int]:
        """在本后端内将文件复制到目标作品，返回 (relpath, name, size)"""

    @abstractmethod
    async def move_within(self, src_relpath: str, target_rj_code: str) -> tuple[str, str, int]:
        """在本后端内将文件移动到目标作品，返回 (relpath, name, size)"""

    # ---------- 文件夹 ----------

    @abstractmethod
    async def list_directory(self, rj_code: str, subpath: str = "") -> tuple[list[tuple[str, int]], list[str]]:
        """列出目录内容。
        返回 (files, folders)：
        - files: [(relpath, size), ...]
        - folders: [relpath, ...]
        relpath 均为相对存储根、含 rj_code 前缀的正斜杠路径。
        """

    @abstractmethod
    async def create_folder(self, rj_code: str, subpath: str, folder_name: str) -> str:
        """创建文件夹，返回 relpath"""

    @abstractmethod
    async def delete_folder(self, rj_code: str, folder_path: str) -> None:
        """递归删除文件夹（folder_path 相对作品根目录）"""

    @abstractmethod
    async def rename_folder(self, rj_code: str, folder_path: str, new_name: str) -> str:
        """重命名文件夹，返回新的 relpath"""
