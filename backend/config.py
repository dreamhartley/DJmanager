"""应用配置模块"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
COVERS_DIR = DATA_DIR / "covers"
WORKS_DIR = DATA_DIR / "works"

# 数据库
DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'database.db'}"

# 封面图片保存目录
COVERS_DIR.mkdir(parents=True, exist_ok=True)
WORKS_DIR.mkdir(parents=True, exist_ok=True)

# 支持的文件类型
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv", ".wmv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".xml", ".csv", ".log", ".py", ".js", ".ts", ".html", ".css", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
PLAYABLE_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
PREVIEWABLE_EXTENSIONS = IMAGE_EXTENSIONS | TEXT_EXTENSIONS

# 流媒体分块大小（1MB）
STREAM_CHUNK_SIZE = 1024 * 1024
