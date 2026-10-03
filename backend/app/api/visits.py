"""Counting visits, without keeping anything that identifies anyone.

A visitor is a one-way hash of their address and browser, salted with a value that is created
with the day and cleared when the day's rows are pruned. So the same person cannot be followed
from one day to the next, and no hash can be turned back into an address. Nothing else is kept.

The count is recorded from the browser rather than from the server's request log, because the
log is mostly not people: crawlers, and this deployment's own uptime ping every ten minutes,
would otherwise be the majority of it. Neither runs JavaScript, so neither is counted here.
"""

import hashlib
from datetime import date, timedelta

from secrets import token_hex
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import VisitsOut
from app.database.models import SiteDay, SiteVisitor
from app.database.session import Database
from app.utils.time import utcnow

# Long enough that a visitor returning later the same day is not counted twice, short enough
# that nothing lingers. The daily totals are kept for good; only the hashes expire.
KEEP_VISITOR_DAYS = 2


def fingerprint(salt: str, ip: str, user_agent: str) -> str:
    return hashlib.sha256(f"{salt}|{ip}|{user_agent}".encode()).hexdigest()


async def _day(session: AsyncSession, today: date) -> SiteDay:
    """Today's row, created on first sight. Two first visitors at once is a draw, not an error."""
    row = await session.get(SiteDay, today)
    if row is None:
        session.add(SiteDay(day=today, salt=token_hex(16), views=0, visitors=0))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
        row = await session.get(SiteDay, today)
    return row


async def _is_new_visitor(session: AsyncSession, today: date, visitor: str) -> bool:
    if await session.get(SiteVisitor, (today, visitor)) is not None:
        return False
    session.add(SiteVisitor(day=today, visitor=visitor))
    try:
        await session.commit()
        return True
    except IntegrityError:  # the same person, twice at once
        await session.rollback()
        return False


async def totals(session: AsyncSession, today: date) -> VisitsOut:
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(case((SiteDay.day == today, SiteDay.visitors), else_=0)), 0),
                func.coalesce(func.sum(case((SiteDay.day == today, SiteDay.views), else_=0)), 0),
                func.coalesce(func.sum(SiteDay.visitors), 0),
                func.coalesce(func.sum(SiteDay.views), 0),
            )
        )
    ).one()
    return VisitsOut(today_visitors=row[0], today_views=row[1], total_visitors=row[2], total_views=row[3])


async def record_visit(session: AsyncSession, ip: str, user_agent: str, today: date) -> VisitsOut:
    day = await _day(session, today)
    new_visitor = await _is_new_visitor(session, today, fingerprint(day.salt or "", ip, user_agent[:200]))
    # Counted in the database rather than in Python, so simultaneous visits cannot overwrite
    # each other's increment.
    await session.execute(
        update(SiteDay)
        .where(SiteDay.day == today)
        .values(views=SiteDay.views + 1, visitors=SiteDay.visitors + (1 if new_visitor else 0))
    )
    await session.commit()
    return await totals(session, today)


async def prune_visitors(db: Database, keep_days: int = KEEP_VISITOR_DAYS) -> int:
    """Drop old hashes and the salts that made them, keeping the daily totals."""
    cutoff = utcnow().date() - timedelta(days=keep_days)
    async with db.sessions() as session:
        result = await session.execute(delete(SiteVisitor).where(SiteVisitor.day < cutoff))
        await session.execute(
            update(SiteDay).where(SiteDay.day < cutoff, SiteDay.salt.is_not(None)).values(salt=None)
        )
        await session.commit()
        return result.rowcount or 0
