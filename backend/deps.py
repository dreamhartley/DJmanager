"""公共依赖注入"""

from services.storage import OverlayStorage, storage_manager


def get_storage() -> OverlayStorage:
    """获取全局 OverlayStorage 单例（由 storage_manager 在 lifespan 中初始化）"""
    return storage_manager.get()
