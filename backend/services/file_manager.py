"""文件管理服务"""

import os
import shutil
from pathlib import Path

from config import WORKS_DIR, COVERS_DIR, AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, IMAGE_EXTENSIONS, TEXT_EXTENSIONS


class FileManagerService:
    """本地文件系统管理"""

    @staticmethod
    def get_work_dir(rj_code: str) -> Path:
        """获取作品文件目录"""
        work_dir = WORKS_DIR / rj_code
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    @staticmethod
    def get_file_type(ext: str) -> str:
        """根据扩展名判断文件类型"""
        ext = ext.lower()
        if ext in AUDIO_EXTENSIONS:
            return "audio"
        elif ext in VIDEO_EXTENSIONS:
            return "video"
        elif ext in IMAGE_EXTENSIONS:
            return "image"
        elif ext in TEXT_EXTENSIONS:
            return "text"
        else:
            return "other"

    @staticmethod
    def get_absolute_path(rj_code: str, relative_path: str) -> Path:
        """获取文件的绝对路径（relative_path 相对于 WORKS_DIR）"""
        return WORKS_DIR / relative_path

    @staticmethod
    def save_uploaded_file(rj_code: str, filename: str, content: bytes, subfolder: str = "") -> tuple[str, int]:
        """保存上传的文件，返回 (相对路径, 文件大小)。
        如果指定 subfolder，文件将保存到该子目录下。"""
        target_dir = WORKS_DIR / rj_code / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        # 处理重名
        base, ext = os.path.splitext(filename)
        target_path = target_dir / filename
        counter = 1
        while target_path.exists():
            target_path = target_dir / f"{base}_{counter}{ext}"
            counter += 1

        target_path.write_bytes(content)
        relative_path = target_path.relative_to(WORKS_DIR).as_posix()
        return relative_path, target_path.stat().st_size

    @staticmethod
    def delete_file(rj_code: str, relative_path: str) -> bool:
        """删除文件（relative_path 相对于 WORKS_DIR）"""
        abs_path = WORKS_DIR / relative_path
        if abs_path.exists() and abs_path.is_file():
            abs_path.unlink()
            return True
        return False

    @staticmethod
    def rename_file(rj_code: str, old_relative_path: str, new_name: str) -> tuple[str, str]:
        """重命名文件，返回 (新相对路径, 新文件名)（old_relative_path 相对于 WORKS_DIR）"""
        old_path = WORKS_DIR / old_relative_path
        if not old_path.exists():
            raise FileNotFoundError(f"文件不存在: {old_relative_path}")

        new_path = old_path.parent / new_name
        if new_path.exists():
            raise FileExistsError(f"目标文件已存在: {new_name}")

        old_path.rename(new_path)
        new_relative = new_path.relative_to(WORKS_DIR).as_posix()
        return new_relative, new_name

    @staticmethod
    def copy_file_to_work(rj_code: str, relative_path: str, target_rj_code: str) -> tuple[str, str, int]:
        """将文件复制到目标作品目录，返回 (新相对路径, 新文件名, 文件大小)（relative_path 相对于 WORKS_DIR）"""
        src_path = WORKS_DIR / relative_path
        if not src_path.exists():
            raise FileNotFoundError(f"源文件不存在: {relative_path}")

        target_dir = WORKS_DIR / target_rj_code
        target_dir.mkdir(parents=True, exist_ok=True)

        base, ext = os.path.splitext(src_path.name)
        target_path = target_dir / src_path.name
        counter = 1
        while target_path.exists():
            target_path = target_dir / f"{base}_{counter}{ext}"
            counter += 1

        shutil.copy2(src_path, target_path)
        new_relative = target_path.relative_to(WORKS_DIR).as_posix()
        return new_relative, target_path.name, target_path.stat().st_size

    @staticmethod
    def move_file_to_work(rj_code: str, relative_path: str, target_rj_code: str) -> tuple[str, str, int]:
        """将文件移动到目标作品目录，返回 (新相对路径, 新文件名, 文件大小)（relative_path 相对于 WORKS_DIR）"""
        src_path = WORKS_DIR / relative_path
        if not src_path.exists():
            raise FileNotFoundError(f"源文件不存在: {relative_path}")

        target_dir = WORKS_DIR / target_rj_code
        target_dir.mkdir(parents=True, exist_ok=True)

        base, ext = os.path.splitext(src_path.name)
        target_path = target_dir / src_path.name
        counter = 1
        while target_path.exists():
            target_path = target_dir / f"{base}_{counter}{ext}"
            counter += 1

        shutil.move(str(src_path), str(target_path))
        new_relative = target_path.relative_to(WORKS_DIR).as_posix()
        return new_relative, target_path.name, target_path.stat().st_size

    @staticmethod
    def delete_work_dir(rj_code: str):
        """删除作品目录及其所有文件（包括封面图片）"""
        work_dir = WORKS_DIR / rj_code
        if work_dir.exists():
            shutil.rmtree(work_dir)

        # 删除对应的封面图片
        for p in COVERS_DIR.glob(f"{rj_code}.*"):
            if p.is_file():
                try:
                    p.unlink()
                except Exception as e:
                    print(f"删除封面失败: {p}, {e}")

    # ========== 文件夹操作 ==========

    @staticmethod
    def list_directory(rj_code: str, subpath: str = "") -> tuple[list[str], list[str]]:
        """列出目录中的文件和文件夹。
        subpath 相对于作品目录。
        返回 (文件名列表, 文件夹名列表)，均为相对于 WORKS_DIR 的路径。
        """
        target_dir = WORKS_DIR / rj_code / subpath
        if not target_dir.exists():
            return [], []

        files = []
        folders = []
        for entry in sorted(target_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            rel = entry.relative_to(WORKS_DIR).as_posix()
            if entry.is_dir():
                folders.append(rel)
            elif entry.is_file():
                files.append(rel)

        return files, folders

    @staticmethod
    def create_folder(rj_code: str, subpath: str, folder_name: str) -> str:
        """创建文件夹，返回相对于 WORKS_DIR 的路径。"""
        target_dir = WORKS_DIR / rj_code / subpath
        new_folder = target_dir / folder_name
        if new_folder.exists():
            raise FileExistsError(f"文件夹已存在: {folder_name}")
        new_folder.mkdir(parents=True)
        return new_folder.relative_to(WORKS_DIR).as_posix()

    @staticmethod
    def delete_folder(rj_code: str, folder_path: str) -> bool:
        """删除文件夹（递归删除）。folder_path 相对于作品根目录。"""
        target = WORKS_DIR / rj_code / folder_path
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")
        # 安全检查：不允许删除作品根目录
        if str(target.resolve()) == str((WORKS_DIR / rj_code).resolve()):
            raise ValueError("不允许删除作品根目录")
        shutil.rmtree(target)
        return True

    @staticmethod
    def rename_folder(rj_code: str, folder_path: str, new_name: str) -> str:
        """重命名文件夹，返回新的相对于 WORKS_DIR 的路径。
        folder_path 相对于作品根目录。"""
        target = WORKS_DIR / rj_code / folder_path
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")
        new_path = target.parent / new_name
        if new_path.exists():
            raise FileExistsError(f"目标已存在: {new_name}")
        target.rename(new_path)
        return new_path.relative_to(WORKS_DIR).as_posix()


file_manager = FileManagerService()
