import pytest

from app.database.session import normalize_database_url

SUPABASE = "postgres.abc:pw@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
ASYNCPG = f"postgresql+asyncpg://{SUPABASE}"


@pytest.mark.parametrize("given", [f"postgres://{SUPABASE}", f"postgresql://{SUPABASE}", ASYNCPG])
def test_any_postgres_form_becomes_asyncpg(given):
    """Hosts hand out all three spellings; SQLAlchemy 2.1 would read the bare ones as psycopg,
    which this project does not install."""
    assert normalize_database_url(given) == ASYNCPG


def test_libpq_only_parameters_are_dropped():
    """asyncpg raises on sslmode and friends; it negotiates TLS by itself."""
    assert normalize_database_url(f"postgresql://{SUPABASE}?sslmode=require") == ASYNCPG
    assert normalize_database_url(f"postgresql://{SUPABASE}?sslmode=require&channel_binding=prefer") == ASYNCPG


def test_real_parameters_survive():
    url = normalize_database_url(f"postgresql://{SUPABASE}?sslmode=require&application_name=ubf")
    assert url == f"{ASYNCPG}?application_name=ubf"


def test_passwords_with_symbols_are_left_alone():
    url = "postgresql://user:p%40ss%2Fword@host:5432/db"
    assert normalize_database_url(url) == "postgresql+asyncpg://user:p%40ss%2Fword@host:5432/db"


@pytest.mark.parametrize("url", ["sqlite+aiosqlite:///./ubf.db", "sqlite+aiosqlite:///:memory:",
                                 "postgresql+psycopg://user:pw@host/db"])
def test_other_urls_are_untouched(url):
    assert normalize_database_url(url) == url
