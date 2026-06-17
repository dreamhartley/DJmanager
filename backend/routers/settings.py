"""存储设置 API 路由（WebDAV 配置）"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import StorageSettings, BrowseEntry, TestConnectionRequest
from services.storage import WebDAVStorage, WebDAVError
from services.storage.manager import (
    storage_manager,
    load_storage_settings,
    save_storage_settings,
)

router = APIRouter(prefix="/api/storage", tags=["存储设置"])


def _cfg_to_settings(cfg: dict[str, str]) -> StorageSettings:
    """DB 配置 dict → StorageSettings（密码转成掩码）"""
    has_password = bool(cfg.get("webdav_password", ""))
    return StorageSettings(
        webdav_enabled=cfg.get("webdav_enabled", "false").lower() == "true",
        webdav_url=cfg.get("webdav_url", ""),
        webdav_username=cfg.get("webdav_username", ""),
        webdav_password="***" if has_password else "",
        webdav_base_path=cfg.get("webdav_base_path", ""),
        default_target=cfg.get("default_target", "webdav"),
    )


@router.get("/settings", response_model=StorageSettings)
async def get_storage_settings(db: AsyncSession = Depends(get_db)):
    """获取存储配置（密码以掩码 *** 返回，未设置则为空）"""
    cfg = await load_storage_settings(db)
    return _cfg_to_settings(cfg)


@router.put("/settings", response_model=StorageSettings)
async def update_storage_settings(
    settings: StorageSettings,
    db: AsyncSession = Depends(get_db),
):
    """保存存储配置并即时重建存储后端（无需重启）"""
    updates = {
        "webdav_enabled": "true" if settings.webdav_enabled else "false",
        "webdav_url": settings.webdav_url,
        "webdav_username": settings.webdav_username,
        "webdav_password": settings.webdav_password,
        "webdav_base_path": settings.webdav_base_path,
        "default_target": settings.default_target,
    }
    cfg = await save_storage_settings(db, updates)
    # 必须 commit 后 storage_manager.rebuild() 才能在新 session 中读到最新配置，
    # 否则 rebuild 会读到旧值，导致 WebDAV 后端未启用、文件仍落本地。
    await db.commit()

    # 重建全局 OverlayStorage（关闭旧 WebDAV client，应用新配置）
    await storage_manager.rebuild()

    return _cfg_to_settings(cfg)


@router.post("/test")
async def test_connection(payload: TestConnectionRequest, db: AsyncSession = Depends(get_db)):
    """使用表单临时凭据测试 WebDAV 连接（不持久化）

    密码处理：前端为已保存配置回显掩码 "***" 或保持空字符串，表示"未修改"，
    此时使用数据库中已保存的真实密码进行测试，避免提示"认证失败"。
    """
    if not payload.url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    password = payload.password
    username = payload.username
    base_path = payload.base_path
    if password in ("", "***"):
        cfg = await load_storage_settings(db)
        # 仅当 URL/用户名与已保存配置一致时才复用密码，避免误用其它账户的密码
        if cfg.get("webdav_url") == payload.url and cfg.get("webdav_username") == payload.username:
            password = cfg.get("webdav_password", "")
        if username == "***":
            username = cfg.get("webdav_username", "")
        if base_path == "***":
            base_path = cfg.get("webdav_base_path", "")

    client = WebDAVStorage(
        url=payload.url,
        username=username,
        password=password,
        base_path=base_path,
    )
    try:
        await client.test_connection()
        return {"ok": True, "message": "连接成功"}
    except WebDAVError as e:
        return {"ok": False, "message": str(e)}
    except Exception as e:
        return {"ok": False, "message": f"连接失败：{e}"}
    finally:
        await client.aclose()


@router.get("/browse", response_model=list[BrowseEntry])
async def browse_folders(
    path: str = Query(default="", description="相对 base_path 的子目录"),
    db: AsyncSession = Depends(get_db),
):
    """基于已保存的 WebDAV 配置浏览子目录（供前端选择作品根目录）

    注意：使用 query 参数会暴露 URL，但此处仅传递相对路径；凭据来自已保存配置。
    若需用临时凭据浏览，前端应改用 POST /api/storage/test 验证后先保存再浏览。
    """
    storage = storage_manager.get()
    if storage.webdav is None:
        raise HTTPException(status_code=400, detail="WebDAV 未启用，请先保存配置")
    try:
        entries = await storage.webdav.browse(path)
        return [BrowseEntry(name=e["name"], path=e["path"]) for e in entries]
    except WebDAVError as e:
        raise HTTPException(status_code=502, detail=str(e))
