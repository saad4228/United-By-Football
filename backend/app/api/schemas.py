from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Health = Literal["working", "checking", "unverified", "offline"]


class TeamOut(BaseModel):
    id: int
    slug: str
    name: str
    short_name: str | None
    tla: str | None
    logo_url: str | None
    country: str | None
    primary_color: str | None
    secondary_color: str | None


class PhotoOut(BaseModel):
    url: str
    page: str | None
    subject: str | None
    author: str | None
    license: str | None
    license_url: str | None


class TeamMediaOut(BaseModel):
    status: str  # pending | ok | partial | none | error
    founded: int | None = None
    stadium: str | None = None
    capacity: int | None = None
    website: str | None = None
    photo: PhotoOut | None = None


class TeamDetailOut(TeamOut):
    media: TeamMediaOut


class CompetitionOut(BaseModel):
    id: int
    slug: str
    code: str | None
    name: str
    short_name: str | None
    country: str | None
    logo_url: str | None
    is_major: bool


class Score(BaseModel):
    home: int | None
    away: int | None


class TopSource(BaseModel):
    label: str
    type: str
    access: str | None = None
    available: bool | None = None
    one_click: bool = False
    watch_url: str | None = None


class SourceSummary(BaseModel):
    top: TopSource | None = None
    total: int = 0
    working: int = 0
    checking: int = 0
    unverified: int = 0
    offline: int = 0


class MatchOut(BaseModel):
    id: int
    slug: str
    status: str
    is_live: bool
    minute: int | None
    minute_display: str | None
    kickoff_time: datetime
    home: TeamOut
    away: TeamOut
    score: Score | None
    competition: CompetitionOut | None
    venue: str | None
    referee: str | None
    sources: SourceSummary


class MatchPage(BaseModel):
    items: list[MatchOut]
    total: int
    limit: int
    offset: int


class Reliability(BaseModel):
    label: str
    uptime_pct: float | None
    checks: int


class SourceInfo(BaseModel):
    key: str
    name: str
    type: str
    domain: str | None
    reliability: Reliability


class SourceLinkOut(BaseModel):
    id: int
    health: Health
    status: str
    error_code: str | None
    message: str | None
    label: str | None
    link_type: str
    language: str | None
    quality: str | None
    last_checked_at: datetime | None
    last_ok_at: datetime | None
    response_time_ms: int | None
    redirect_hops: int
    watch_url: str | None
    source: SourceInfo
    regions: list[str] | None = None
    access: str | None = None
    coverage: str | None = None
    notes: str | None = None
    confirmed: bool | None = None
    available: bool | None = None  # for the viewer's country; None when unknown
    one_click: bool = False


class MatchSources(BaseModel):
    country: str | None = None
    match_id: int
    checked_at: datetime
    summary: SourceSummary
    items: list[SourceLinkOut]


class Featured(BaseModel):
    mode: Literal["live", "next", "always_on"]
    match: MatchOut | None


class CompetitionWithCounts(CompetitionOut):
    live_count: int
    upcoming_count: int


class HomeOut(BaseModel):
    server_time: datetime
    demo_mode: bool
    layout: Literal["featured_first", "live_first"]
    featured: Featured
    live: list[MatchOut]
    next_matches: list[MatchOut]
    competitions: list[CompetitionWithCounts]
    popular_teams: list[TeamOut]


class SearchOut(BaseModel):
    query: str
    teams: list[TeamOut]
    competitions: list[CompetitionOut]
    matches: list[MatchOut]


class MetaOut(BaseModel):
    name: str
    version: str
    demo_mode: bool
    server_time: datetime
    refresh_seconds: dict[str, int]
