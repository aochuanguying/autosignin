import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.collector import start_collector, get_status
from app.routes import router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时开始数据采集，关闭时停止。"""
    task = asyncio.create_task(start_collector())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Monitor Dashboard", lifespan=lifespan)

# 注册 API 路由
app.include_router(router)

# 静态文件（前端 HTML/CSS/JS）— 放在路由之后，作为 fallback
static_dir = Path(__file__).parent.parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
