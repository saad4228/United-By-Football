from collections.abc import AsyncIterator

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    is_sqlite = database_url.startswith("sqlite")
    engine = create_async_engine(
        database_url,
        connect_args={"timeout": 30} if is_sqlite else {},
        pool_pre_ping=not is_sqlite,
    )
    if is_sqlite:

        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
            cursor = dbapi_connection.cursor()
            if ":memory:" not in database_url:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


def _add_missing_columns(sync_conn) -> None:
    """create_all() never alters existing tables. Until proper migrations exist, add any new
    *nullable* columns the models declare, so upgrading keeps existing data."""
    inspector = inspect(sync_conn)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing or not column.nullable or column.primary_key:
                continue
            ddl = column.type.compile(dialect=sync_conn.dialect)
            sync_conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl}"))


class Database:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_add_missing_columns)

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session
