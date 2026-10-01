"""Connector discovery: every package under connectors/{web,api,app}/<name>/adapter.py
that exposes a ``CONNECTOR`` class is registered automatically. A connector that
fails to import is logged and skipped, never taking the others down with it."""

import importlib
import logging
import pkgutil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.connectors.base import SourceConnector
from app.database.models import Source

log = logging.getLogger(__name__)
_FAMILIES = ("web", "api", "app")


def discover_connector_classes() -> list[type[SourceConnector]]:
    classes: list[type[SourceConnector]] = []
    for family in _FAMILIES:
        package = importlib.import_module(f"app.connectors.{family}")
        for info in pkgutil.iter_modules(package.__path__):
            if not info.ispkg:
                continue
            module_name = f"app.connectors.{family}.{info.name}.adapter"
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                if exc.name == module_name:
                    continue  # package without an adapter yet
                log.exception("connector %s failed to import", module_name)
                continue
            except Exception:
                log.exception("connector %s failed to import", module_name)
                continue
            cls = getattr(module, "CONNECTOR", None)
            if isinstance(cls, type) and issubclass(cls, SourceConnector):
                classes.append(cls)
    return sorted(classes, key=lambda c: c.key)


def build_connectors(settings: Settings) -> list[SourceConnector]:
    return [cls() for cls in discover_connector_classes() if cls.enabled(settings)]


async def sync_sources(session: AsyncSession, connectors: list[SourceConnector]) -> dict[str, Source]:
    """Make sure every active connector has a row in `sources` (admins can disable it there)."""
    existing = {s.key: s for s in (await session.scalars(select(Source))).all()}
    for connector in connectors:
        source = existing.get(connector.key)
        if source is None:
            source = Source(key=connector.key, enabled=True)
            session.add(source)
            existing[connector.key] = source
        source.name = connector.name
        source.domain = connector.domain
        source.connector_type = connector.connector_type
        source.description = connector.description
        source.min_check_interval = connector.min_check_interval
    await session.commit()
    return existing
