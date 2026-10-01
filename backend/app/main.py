import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import admin, public
from app.config import Settings, get_settings
from app.database.session import Database
from app.demo import mock_sources
from app.scheduler.engine import Engine
from app.utils.ratelimit import SlidingWindowLimiter

log = logging.getLogger("ubf")
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.database_url)
        engine = Engine(settings, db)
        app.state.settings, app.state.db, app.state.engine = settings, db, engine
        app.state.admin_token = settings.admin_token or secrets.token_urlsafe(18)
        if not settings.admin_token:
            log.warning("UBF_ADMIN_TOKEN not set; generated admin token for this run: %s", app.state.admin_token)
        await engine.bootstrap()
        if settings.scheduler_enabled:
            engine.start()
        log.info("United By Football %s ready (demo_mode=%s, connectors=%s)", __version__, settings.demo_mode,
                 [c.key for c in engine.connectors])
        try:
            yield
        finally:
            await engine.stop()
            await db.dispose()

    app = FastAPI(title="United By Football API", version=__version__, lifespan=lifespan)
    app.state.limiter = SlidingWindowLimiter()
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(public.router)
    app.include_router(admin.router)
    if settings.demo_mode:
        app.include_router(mock_sources.router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"ok": True}

    if settings.serve_frontend and (FRONTEND_DIST / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
        index = FRONTEND_DIST / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith(("api/", "mock-sources/")):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            candidate = (FRONTEND_DIST / path).resolve()
            if path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index)

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
