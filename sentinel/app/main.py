"""Sentinel — FastAPI application entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import feedback as feedback_api
from app.api import sources as sources_api
from app.pages import dashboard
from app.pages import quality
from app.pages import videos


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Sentinel", lifespan=lifespan)

# Static files (CSS, images — minimal, Tailwind via CDN in dev)
_static_dir = Path(__file__).parent.parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Routers
app.include_router(dashboard.router)
app.include_router(videos.router)
app.include_router(quality.router)
app.include_router(sources_api.router, prefix="/api")
app.include_router(feedback_api.router, prefix="/api")
