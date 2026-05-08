"""DJmanager - 同人音声管理/刮削器 后端入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import DATA_DIR, COVERS_DIR
from database import init_db
from routers.works import router as works_router
from routers.files import router as files_router
from routers.chunked_upload import router as chunked_upload_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    await init_db()
    yield


app = FastAPI(
    title="DJmanager",
    description="同人音声管理/刮削器 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置（开发环境允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件挂载：封面图片
app.mount("/covers", StaticFiles(directory=str(COVERS_DIR)), name="covers")

# 注册路由
app.include_router(works_router)
app.include_router(files_router)
app.include_router(chunked_upload_router)


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
