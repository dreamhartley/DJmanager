"""存储后端抽象层

- `Storage`：统一异步接口（基类）
- `LocalStorage`：本地文件系统实现
- `WebDAVStorage`：基于 httpx 的 WebDAV 实现
- `OverlayStorage`：本地 + WebDAV 叠加，按 rj_code 解析实际后端
"""

from .base import Storage, get_file_type
from .local import LocalStorage
from .webdav import WebDAVStorage, WebDAVError
from .overlay import OverlayStorage

__all__ = [
    "Storage",
    "LocalStorage",
    "WebDAVStorage",
    "WebDAVError",
    "OverlayStorage",
    "get_file_type",
    "storage_manager",
    "walk_work_files",
]

# manager 导入 OverlayStorage 等模块，放在后面避免循环导入
from .manager import storage_manager, walk_work_files  # noqa: E402
