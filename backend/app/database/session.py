from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base

# Managed Postgres providers hand out libpq-style URLs. SQLAlchemy 2.1 reads a bare
# "postgresql://" as the psycopg driver, which this project doesn't ship, and asyncpg rejects
# libpq's query parameters outright. Rather than make every deployment remember to rewrite the
# string, accept what the provider gives and normalise it here.
_LIBPQ_ONLY = {"sslmode", "channel_binding", "target_session_attrs", "gssencmode", "options"}


def normalize_database_url(url: str) -> str:
    """Accept a Postgres URL in any of the forms a host might give, and return one asyncpg
    understands. SQLite URLs and anything already explicit are passed through untouched.

    asyncpg negotiates TLS on its own, so dropping `sslmode` does not make the connection
    insecure - a server that requires TLS still gets it.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break
    if not url.startswith("postgresql+asyncpg://"):
        return url
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in _LIBPQ_ONLY]
    return urlunsplit(parts._replace(query=urlencode(kept)))


def create_engine(database_url: str) -> AsyncEngine:
    database_url = normalize_database_url(database_url)
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
