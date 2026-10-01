import math
import secrets
from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.scheduler.engine import Engine


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db.sessions() as session:
        yield session


def client_ip(request: Request) -> str:
    settings: Settings = request.app.state.settings
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(group: str):
    def dependency(request: Request) -> None:
        settings: Settings = request.app.state.settings
        limit = getattr(settings, f"rate_limit_{group}")
        retry = request.app.state.limiter.hit(f"{group}:{client_ip(request)}", limit)
        if retry is not None:
            raise HTTPException(429, "Too many requests", headers={"Retry-After": str(math.ceil(retry))})

    return Depends(dependency)


def require_admin(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    expected: str = request.app.state.admin_token
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "Admin token required")
