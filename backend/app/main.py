from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

from .config import settings
from .agent import build_explainer
from .repository import get_repo
from .routes_pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo = await get_repo()
    app.state.repo = repo

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=settings.playwright_headless)
    app.state.playwright = pw
    app.state.browser = browser

    # agent hook (optional)
    app.state.explain_delta = build_explainer()

    try:
        yield
    finally:
        await browser.close()
        await pw.stop()


app = FastAPI(title="WebDelta API", version="2.0.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pages_router)


@app.get("/health")
async def health():
    return {"ok": True}

