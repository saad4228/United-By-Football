"""WEB PAGE connector: scrapes a cluttered HTML "stream guide" listing.

Points at the bundled demo page (/mock-sources/listing). It is the reference
example for HTML connectors: fetch -> parse -> emit normalized listings, and let
the shared pipeline do matching, resolution and validation.
"""

from datetime import datetime

from bs4 import BeautifulSoup

from app.config import Settings
from app.connectors.base import ConnectorContext, DiscoveredLink, DiscoveredMatch, SourceConnector
from app.database.models import ConnectorType
from app.utils.text import sanitize_text

_SEPARATORS = (" vs. ", " vs ", " v ", " - ", " – ", " x ")


def split_title(title: str) -> tuple[str, str] | None:
    lowered = title.lower()
    for sep in _SEPARATORS:
        idx = lowered.find(sep)
        if idx > 0:
            return title[:idx].strip(), title[idx + len(sep):].strip()
    return None


def parse_listing(html: str) -> list[DiscoveredMatch]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.select(".event-row"):
        title_el = row.select_one(".event-title")
        title = sanitize_text(title_el.get_text(" ") if title_el else None, 200)
        teams = split_title(title) if title else None
        if not teams:
            continue
        kickoff = None
        time_el = row.select_one("time[datetime]")
        if time_el:
            try:
                kickoff = datetime.fromisoformat(str(time_el["datetime"]))
            except ValueError:
                kickoff = None
        league_el = row.select_one(".league")
        links = [
            DiscoveredLink(
                url=str(a["href"]),
                label=sanitize_text(a.get_text(" "), 60),
                language=sanitize_text(a.get("data-lang"), 40),
                quality=sanitize_text(a.get("data-quality"), 20),
            )
            for a in row.select("a.stream-link[href]")
        ]
        results.append(
            DiscoveredMatch(
                home=teams[0],
                away=teams[1],
                kickoff=kickoff,
                competition=sanitize_text(league_el.get_text(" "), 60) if league_el else None,
                links=links,
            )
        )
    return results


class DemoListingConnector(SourceConnector):
    key = "demo-stream-guide"
    name = "Stream Guide (demo)"
    connector_type = ConnectorType.WEB
    domain = "demo.local"
    description = "Demo HTML listing page with nicknamed teams and an interstitial redirect layer."
    offline_markers = ("stream not found", "stream is offline")

    @classmethod
    def enabled(cls, settings: Settings) -> bool:
        return settings.demo_mode

    async def discover(self, ctx: ConnectorContext) -> list[DiscoveredMatch]:
        response = await ctx.get(f"{ctx.settings.demo_source_base_url}/listing")
        return parse_listing(response.text)


CONNECTOR = DemoListingConnector
