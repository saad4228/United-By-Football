from datetime import timedelta

from sqlalchemy import select

from app.api.visits import KEEP_VISITOR_DAYS, fingerprint, prune_visitors
from app.database.models import SiteDay, SiteVisitor
from app.utils.time import utcnow

CHROME = {"user-agent": "Mozilla/5.0 Chrome/120"}
FIREFOX = {"user-agent": "Mozilla/5.0 Firefox/121"}


async def test_a_returning_visitor_adds_a_view_but_not_a_visitor(client):
    first = (await client.post("/api/visit", headers=CHROME)).json()
    assert (first["today_views"], first["today_visitors"]) == (1, 1)

    again = (await client.post("/api/visit", headers=CHROME)).json()
    assert again["today_views"] == 2, "a second page load is a second view"
    assert again["today_visitors"] == 1, "but the same person is not a second visitor"

    other = (await client.post("/api/visit", headers=FIREFOX)).json()
    assert (other["today_views"], other["today_visitors"]) == (3, 2)
    assert (other["total_views"], other["total_visitors"]) == (3, 2)


async def test_no_address_is_stored(app, client):
    await client.post("/api/visit", headers=CHROME)
    async with app.state.db.sessions() as session:
        rows = (await session.scalars(select(SiteVisitor))).all()
    assert len(rows) == 1
    assert len(rows[0].visitor) == 64 and all(c in "0123456789abcdef" for c in rows[0].visitor)


def test_the_same_person_hashes_differently_each_day():
    """The salt is per day, so yesterday's hash cannot be matched against today's."""
    assert fingerprint("monday-salt", "1.2.3.4", "Chrome") != fingerprint("tuesday-salt", "1.2.3.4", "Chrome")
    assert fingerprint("salt", "1.2.3.4", "Chrome") == fingerprint("salt", "1.2.3.4", "Chrome")


async def test_pruning_drops_the_hashes_and_salt_but_keeps_the_count(app, client):
    await client.post("/api/visit", headers=CHROME)
    old = utcnow().date() - timedelta(days=KEEP_VISITOR_DAYS + 1)
    async with app.state.db.sessions() as session:
        session.add(SiteDay(day=old, salt="a-salt-from-last-week", views=40, visitors=9))
        session.add(SiteVisitor(day=old, visitor="f" * 64))
        await session.commit()

    assert await prune_visitors(app.state.db) == 1

    async with app.state.db.sessions() as session:
        assert (await session.scalars(select(SiteVisitor.day))).all() == [utcnow().date()], "only today's hashes remain"
        stale = await session.get(SiteDay, old)
        assert stale.salt is None, "the salt goes with the hashes it made"
        assert (stale.views, stale.visitors) == (40, 9), "the totals are kept"

    totals = (await client.post("/api/visit", headers=CHROME)).json()
    assert totals["total_views"] == 42 and totals["total_visitors"] == 10
