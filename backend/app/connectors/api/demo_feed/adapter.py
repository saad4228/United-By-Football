"""API connector: consumes a JSON event feed that uses three-letter team codes."""

from datetime import datetime

from app.config import Settings
from app.connectors.base import ConnectorContext, DiscoveredLink, DiscoveredMatch, SourceConnector
from app.database.models import ConnectorType
from app.utils.text import sanitize_text


def parse_events(payload: dict) -> list[DiscoveredMatch]:
    results = []
    for event in payload.get("events", []):
        home, away = sanitize_text(event.get("home"), 80), sanitize_text(event.get("away"), 80)
        if not home or not away:
            continue
        try:
            kickoff = datetime.fromisoformat(event["start"]) if event.get("start") else None
        except (TypeError, ValueError):
            kickoff = None
        links = [
            DiscoveredLink(
                url=str(s["url"]),
                label=sanitize_text(s.get("name"), 60),
                language=sanitize_text(s.get("lang"), 40),
                quality=sanitize_text(s.get("quality"), 20),
            )
            for s in event.get("streams", [])
            if isinstance(s, dict) and s.get("url")
        ]
        results.append(
            DiscoveredMatch(
                home=home,
                away=away,
                kickoff=kickoff,
                competition=sanitize_text(event.get("competition"), 80),
                links=links,
            )
        )
    return results


class DemoFeedConnector(SourceConnector):
    key = "demo-event-feed"
    name = "Event Feed (demo)"
    connector_type = ConnectorType.API
    domain = "demo.local"
    description = "Demo JSON API with three-letter team codes and approximate kickoff times."

    @classmethod
    def enabled(cls, settings: Settings) -> bool:
        return settings.demo_mode

    async def discover(self, ctx: ConnectorContext) -> list[DiscoveredMatch]:
        response = await ctx.get(f"{ctx.settings.demo_source_base_url}/api/events")
        return parse_events(response.json())


CONNECTOR = DemoFeedConnector
