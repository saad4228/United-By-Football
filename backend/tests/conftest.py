import httpx
import pytest

from app.config import Settings
from app.main import create_app


async def fake_dns(host: str, port: int) -> list[str]:
    """Pretend every public hostname resolves to a public address; no real DNS in tests."""
    return ["93.184.215.14"]


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        scheduler_enabled=False,
        serve_frontend=False,
        demo_mode=True,
        espn_enabled=False,
        admin_token="test-admin",
        public_base_url="http://127.0.0.1:8000",
    )


@pytest.fixture
async def app(settings):
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        engine = application.state.engine
        # Route every outbound request back into the app itself: the demo sources are served
        # in-process, and nothing in the test suite touches the real network.
        await engine.checker_http.aclose()
        engine.checker_http = httpx.AsyncClient(transport=httpx.ASGITransport(app=application), timeout=5)
        engine.resolver.client = engine.checker_http
        engine.guard.resolver = fake_dns
        yield application


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def admin_headers() -> dict:
    return {"X-Admin-Token": "test-admin"}
