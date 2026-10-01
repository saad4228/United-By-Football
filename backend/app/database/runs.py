from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CrawlRun
from app.utils.time import utcnow


async def start_run(session: AsyncSession, job: str, connector_key: str | None) -> CrawlRun:
    run = CrawlRun(job=job, connector_key=connector_key, started_at=utcnow(), status="running")
    session.add(run)
    await session.flush()
    return run


def finish_run(run: CrawlRun, status: str = "ok", error: str | None = None, error_code: str | None = None) -> None:
    run.status = status
    run.finished_at = utcnow()
    run.error = error[:2000] if error else None
    run.error_code = error_code
