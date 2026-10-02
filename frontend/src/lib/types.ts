/**
 * API types.
 *
 * These are not hand-written: every shape below is an alias into `api-schema.ts`, which is
 * generated from the backend's own OpenAPI document (`npm run types:api`). Rename or retype a
 * field in the Python models and the frontend stops compiling, instead of breaking quietly for
 * users at runtime.
 *
 * Import from here rather than from `api-schema` directly - these names read better and keep
 * the generated file an implementation detail.
 */
import type { components } from "./api-schema";

type S = components["schemas"];

export type Team = S["TeamOut"];
export type TeamMedia = S["TeamMediaOut"];
export type TeamDetail = S["TeamDetailOut"];

export type Competition = S["CompetitionOut"];
export type CompetitionWithCounts = S["CompetitionWithCounts"];

export type Access = NonNullable<S["SourceLinkOut"]["access"]>;
export type Coverage = NonNullable<S["SourceLinkOut"]["coverage"]>;
export type Health = S["SourceLinkOut"]["health"];
export type TopSource = S["TopSource"];
export type SourceSummary = S["SourceSummary"];
export type SourceLink = S["SourceLinkOut"];
export type MatchSources = S["MatchSources"];

export type MatchStatus = S["MatchOut"]["status"];
export type Match = S["MatchOut"];
export type MatchPage = S["MatchPage"];

export type Player = S["PlayerOut"];
export type Lineup = S["LineupOut"];
export type MatchEvent = S["EventOut"];
export type StatKey = S["StatOut"]["key"];
export type FormGame = S["FormGame"];
export type MatchDetails = S["MatchDetailsOut"];

export type TableNote = S["TableNote"];
export type TableRow = S["TableRow"];
export type LeagueTable = S["TableOut"];

export type Home = S["HomeOut"];
export type SearchResult = S["SearchOut"];
export type Meta = S["MetaOut"];
