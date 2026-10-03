from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.utils.time import utcnow


class UTCDateTime(TypeDecorator):
    """Stores naive UTC, always returns timezone-aware UTC (portable across SQLite/Postgres)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    HALFTIME = "halftime"
    FINISHED = "finished"
    POSTPONED = "postponed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


LIVE_STATUSES = (MatchStatus.LIVE, MatchStatus.HALFTIME)


class LinkStatus(StrEnum):
    DISCOVERED = "discovered"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    ERROR = "error"


class ConnectorType(StrEnum):
    WEB = "web"
    API = "api"
    APP = "app"
    USER = "user"
    OFFICIAL = "official"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Competition(TimestampMixin, Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    code: Mapped[str | None] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(80))
    logo_url: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    is_major: Mapped[bool] = mapped_column(Boolean, default=False)
    # National-team competitions (Nations League, friendlies, qualifiers), for the Internationals filter.
    national_teams: Mapped[bool | None] = mapped_column(Boolean, default=False)
    # ESPN league slug (e.g. "eng.1"), used to fetch the league table.
    espn_league: Mapped[str | None] = mapped_column(String(40))


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[str | None] = mapped_column(String(60))
    tla: Mapped[str | None] = mapped_column(String(5))
    logo_url: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(80))
    primary_color: Mapped[str | None] = mapped_column(String(9))
    secondary_color: Mapped[str | None] = mapped_column(String(9))
    popularity: Mapped[int] = mapped_column(Integer, default=0)

    aliases: Mapped[list["TeamAlias"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class TeamAlias(Base):
    __tablename__ = "team_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(120), unique=True, index=True)  # normalized form

    team: Mapped[Team] = relationship(back_populates="aliases")


class TeamExternalRef(Base):
    __tablename__ = "team_external_refs"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_team_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(80))


class TeamMedia(Base):
    """Banner photo and club facts, looked up once per team and refreshed monthly."""

    __tablename__ = "team_media"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))  # ok | partial | none | error
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # Hand-picked entry: the automatic lookup leaves it alone, so a curated banner stays put.
    locked: Mapped[bool | None] = mapped_column(Boolean, default=False)
    sportsdb_id: Mapped[str | None] = mapped_column(String(20))
    founded: Mapped[int | None] = mapped_column(Integer)
    stadium: Mapped[str | None] = mapped_column(String(160))
    capacity: Mapped[int | None] = mapped_column(Integer)
    website: Mapped[str | None] = mapped_column(String(255))
    photo_url: Mapped[str | None] = mapped_column(Text)
    photo_page: Mapped[str | None] = mapped_column(Text)
    photo_subject: Mapped[str | None] = mapped_column(String(200))
    photo_author: Mapped[str | None] = mapped_column(String(200))
    photo_license: Mapped[str | None] = mapped_column(String(60))
    photo_license_url: Mapped[str | None] = mapped_column(Text)


class Match(TimestampMixin, Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    competition_id: Mapped[int | None] = mapped_column(ForeignKey("competitions.id"), index=True)
    kickoff_time: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default=MatchStatus.SCHEDULED, index=True)
    score_home: Mapped[int | None] = mapped_column(Integer)
    score_away: Mapped[int | None] = mapped_column(Integer)
    minute: Mapped[int | None] = mapped_column(Integer)
    minute_display: Mapped[str | None] = mapped_column(String(12))
    venue: Mapped[str | None] = mapped_column(String(160))
    referee: Mapped[str | None] = mapped_column(String(120))
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])
    competition: Mapped[Competition | None] = relationship()
    external_refs: Mapped[list["MatchExternalRef"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class MatchExternalRef(Base):
    __tablename__ = "match_external_refs"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_match_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(120))

    match: Mapped[Match] = relationship(back_populates="external_refs")


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str | None] = mapped_column(String(255))
    connector_type: Mapped[str] = mapped_column(String(16), default=ConnectorType.WEB)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    min_check_interval: Mapped[int | None] = mapped_column(Integer)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)


class StreamLink(TimestampMixin, Base):
    __tablename__ = "stream_links"
    __table_args__ = (UniqueConstraint("match_id", "source_id", "url_hash", name="uq_link"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    original_url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64))
    resolved_url: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(120))
    link_type: Mapped[str] = mapped_column(String(20), default="watch")
    language: Mapped[str | None] = mapped_column(String(40))
    quality: Mapped[str | None] = mapped_column(String(20))
    quality_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Where and how the source can be watched. regions: comma-separated ISO country codes,
    # "*" for worldwide, "!XX" to exclude a country. None = unknown.
    regions: Mapped[str | None] = mapped_column(String(400))
    access: Mapped[str | None] = mapped_column(String(20))  # free | free_account | licence | subscription
    coverage: Mapped[str | None] = mapped_column(String(20))  # all | selected
    notes: Mapped[str | None] = mapped_column(String(200))
    # True when this specific match is known to be on the source (e.g. its YouTube video was found).
    confirmed: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(16), default=LinkStatus.DISCOVERED, index=True)
    error_code: Mapped[str | None] = mapped_column(String(40))
    http_status: Mapped[int | None] = mapped_column(Integer)
    redirect_hops: Mapped[int] = mapped_column(Integer, default=0)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    check_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)

    match: Mapped[Match] = relationship()
    source: Mapped[Source] = relationship()


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("stream_links.id", ondelete="CASCADE"), index=True)
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(16))
    http_status: Mapped[int | None] = mapped_column(Integer)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(80))
    resolved_url: Mapped[str | None] = mapped_column(Text)


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(20), index=True)  # fixtures | discovery | health
    connector_key: Mapped[str | None] = mapped_column(String(80), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | ok | error
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    unmatched: Mapped[int] = mapped_column(Integer, default=0)
    links_new: Mapped[int] = mapped_column(Integer, default=0)
    links_updated: Mapped[int] = mapped_column(Integer, default=0)
    links_expired: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text)


class LinkClick(Base):
    __tablename__ = "link_clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("stream_links.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    link_status: Mapped[str] = mapped_column(String(16))
    clicked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
