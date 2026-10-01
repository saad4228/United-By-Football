from functools import lru_cache
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UBF_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./ubf.db"
    demo_mode: bool = False
    public_base_url: str = "http://127.0.0.1:8000"
    football_data_api_key: str | None = None
    # ESPN's public scoreboard feed: real fixtures, live scores, crests and kit colours, no key.
    espn_enabled: bool = True
    # Comma-separated ESPN league slugs; empty means the built-in list (see match/providers/espn.py).
    espn_leagues: str = ""
    espn_concurrency: int = 6
    # Team banners and club facts: stadium photos from Wikimedia Commons, facts from TheSportsDB.
    # Optional YouTube Data API key: lets free YouTube channels link straight to the match's
    # live video instead of the channel's streams page (free key from Google Cloud).
    youtube_api_key: str | None = None
    media_enabled: bool = True
    sportsdb_key: str = "123"  # TheSportsDB's public free key
    # How this deployment identifies itself to Wikimedia (their API policy requires a contact
    # URL or email in the User-Agent). Defaults to the public base URL; set a real one in production.
    contact: str | None = None
    admin_token: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    trust_proxy_headers: bool = False
    scheduler_enabled: bool = True
    serve_frontend: bool = True

    # Link resolution / validation
    resolver_max_redirects: int = 5
    resolver_timeout_seconds: float = 8.0
    resolver_max_body_bytes: int = 65_536
    resolver_allowed_ports: str = "80,443"
    # host or host:port entries exempt from private-address blocking. Development only.
    resolver_allow_hosts: str = ""
    resolver_user_agent: str = "UnitedByFootballBot/0.1 (+link-health-checker)"
    health_concurrency: int = 8
    health_per_host_concurrency: int = 2

    # Cadence (seconds)
    health_tick: int = 10
    health_live_interval: int = 30
    health_soon_interval: int = 120
    health_default_interval: int = 900
    discovery_tick: int = 30
    discovery_hot_interval: int = 120
    discovery_warm_interval: int = 300
    discovery_cold_interval: int = 900
    fixtures_live_interval: int = 30
    fixtures_idle_interval: int = 600

    # Public API rate limits (requests per minute per client)
    rate_limit_search: int = 60
    rate_limit_matches: int = 240
    rate_limit_sources: int = 240

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_ports(self) -> set[int]:
        return {int(p) for p in self.resolver_allowed_ports.split(",") if p.strip()}

    @property
    def contact_url(self) -> str:
        return self.contact or f"{self.public_base_url.rstrip('/')}/about"

    @property
    def demo_source_base_url(self) -> str:
        return self.public_base_url.rstrip("/") + "/mock-sources"

    @property
    def allow_hosts(self) -> set[str]:
        hosts = {h.strip().lower() for h in self.resolver_allow_hosts.split(",") if h.strip()}
        if self.demo_mode:
            # The demo connectors point at this backend's own /mock-sources routes, which live
            # on a loopback address. Only that exact host:port is exempted, and only in demo mode.
            parts = urlsplit(self.public_base_url)
            if parts.hostname:
                port = parts.port or (443 if parts.scheme == "https" else 80)
                hosts.add(f"{parts.hostname.lower()}:{port}")
        return hosts


@lru_cache
def get_settings() -> Settings:
    return Settings()
