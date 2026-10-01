from app.config import Settings
from app.match.providers.base import FixtureProvider
from app.match.providers.demo import DemoFixtureProvider
from app.match.providers.espn import ESPNProvider
from app.match.providers.football_data import FootballDataProvider


def build_providers(settings: Settings) -> list[FixtureProvider]:
    if DemoFixtureProvider.enabled(settings):
        # Demo mode is self-contained: never mix synthetic fixtures with real ones.
        return [DemoFixtureProvider()]
    providers: list[FixtureProvider] = []
    if ESPNProvider.enabled(settings):
        providers.append(ESPNProvider.from_settings(settings))
    if FootballDataProvider.enabled(settings):
        providers.append(FootballDataProvider(settings.football_data_api_key or ""))
    return providers
