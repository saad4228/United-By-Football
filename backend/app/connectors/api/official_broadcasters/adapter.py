"""OFFICIAL FEED connector: licensed rights holders per competition.

Reads a curated registry (registry.json) instead of crawling anything, and attaches
the rights holders' official pages to every known match in that competition. This
is the model the platform should prefer: authorized destinations first.
"""

import json
from datetime import timedelta
from pathlib import Path

from app.connectors.base import ConnectorContext, DiscoveredLink, DiscoveredMatch, SourceConnector
from app.database.models import ConnectorType
from app.utils.text import sanitize_text

REGISTRY_PATH = Path(__file__).with_name("registry.json")
REGION_CODES = {"US": ["US"], "UK": ["GB"], "Global": ["*"]}
HORIZON = timedelta(days=3)


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, list)}


class OfficialBroadcastersConnector(SourceConnector):
    key = "official-broadcasters"
    name = "Official broadcasters"
    connector_type = ConnectorType.OFFICIAL
    domain = None
    description = "Curated registry of licensed rights holders per competition and region."
    # Broadcaster landing pages are static; check them rarely.
    min_check_interval = 1800
    unverifiable_errors = ("TIMEOUT", "CONNECTION_ERROR")
    # Rights holders geo-redirect visitors outside their territory. Our checker's region
    # is not the viewer's, so that means "can't verify from here", not "offline".
    geo_block_url_markers = ("/unavailable", "/not-available", "/geo-block", "/geoblock")

    async def discover(self, ctx: ConnectorContext) -> list[DiscoveredMatch]:
        registry = load_registry()
        results = []
        for match in ctx.matches:
            entries = registry.get(match.competition_code or "")
            if not entries or match.status in ("finished", "cancelled"):
                continue
            if match.kickoff > ctx.now + HORIZON:
                continue
            links = [
                DiscoveredLink(
                    url=entry["url"],
                    label=sanitize_text(f"{entry['name']} ({entry['region']})", 60),
                    link_type="official",
                    language=sanitize_text(entry.get("language"), 40),
                    regions=REGION_CODES.get(entry.get("region", ""), [entry.get("region", "")]),
                    access="subscription",
                )
                for entry in entries
                if entry.get("url") and entry.get("name")
            ]
            results.append(
                DiscoveredMatch(home=match.home, away=match.away, kickoff=match.kickoff, links=links,
                                match_id=match.id)
            )
        return results


CONNECTOR = OfficialBroadcastersConnector
