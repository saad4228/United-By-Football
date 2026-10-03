"""Export team banners and club facts as SQL that can be replayed into another database.

Banner lookups are slow on purpose: Wikimedia and TheSportsDB are called at polite rates, so
rebuilding them from nothing takes hours. Gathering them once and replaying them is far kinder
to both services, and it means moving the database costs nothing.

    python scripts/export_team_media.py --out ../transfer-banners.sql

Rows are matched on the team's slug, because row ids differ between databases. Re-running is
safe: existing rows are updated. Anything with a photo arrives `locked`, so the background
lookup leaves it alone; rows without one arrive due for a retry, so the search carries on.
"""

import argparse
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone

COLUMNS = ("status", "sportsdb_id", "founded", "stadium", "capacity", "website", "photo_url",
           "photo_page", "photo_subject", "photo_author", "photo_license", "photo_license_url")
TARGET = ("status", "checked_at", *COLUMNS[1:], "locked")
BATCH = 150  # keeps each statement small enough to paste into a browser SQL console
PHOTO = COLUMNS.index("photo_url")


def literal(value: object) -> str:
    """A Postgres text literal, or NULL. Every value is cast on the way in, so text is enough."""
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def statements(rows: list[tuple]) -> list[str]:
    out = []
    for start in range(0, len(rows), BATCH):
        values = []
        for slug, *rest in rows[start:start + BATCH]:
            locked = "true" if rest[PHOTO] else "false"
            values.append("  (" + ", ".join([literal(slug), *(literal(v) for v in rest), locked]) + ")")
        out.append("\n".join([
            f"INSERT INTO team_media ({', '.join(('team_id', *TARGET))})",
            "SELECT t.id, v.status,",
            # A locked row is never looked up again, so its timestamp only records when it
            # arrived. An unlocked one is backdated past the retry window so the hunt resumes.
            "       (now() AT TIME ZONE 'utc')"
            " - (CASE WHEN v.locked THEN interval '0' ELSE interval '8 days' END),",
            "       v.sportsdb_id, v.founded::int, v.stadium, v.capacity::int, v.website,",
            "       v.photo_url, v.photo_page, v.photo_subject, v.photo_author,",
            "       v.photo_license, v.photo_license_url, v.locked",
            "FROM (VALUES",
            ",\n".join(values),
            f") AS v(slug, {', '.join(COLUMNS)}, locked)",
            "JOIN teams t ON t.slug = v.slug",
            "ON CONFLICT (team_id) DO UPDATE SET",
            ",\n".join(f"  {c} = EXCLUDED.{c}" for c in TARGET) + ";",
            "",
        ]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="ubf.db", help="SQLite file to read (default: ubf.db)")
    parser.add_argument("--out", default="transfer-banners.sql", help="file to write")
    args = parser.parse_args()

    rows = sqlite3.connect(args.database).execute(
        f"SELECT t.slug, {', '.join('m.' + c for c in COLUMNS)} FROM team_media m"
        " JOIN teams t ON t.id = m.team_id ORDER BY t.slug"
    ).fetchall()
    if not rows:
        print(f"no team_media rows in {args.database}", file=sys.stderr)
        return 1

    photos = sum(1 for row in rows if row[PHOTO + 1])
    header = [
        f"-- Team banners and club facts: {len(rows)} teams, {photos} with a photo.",
        f"-- Exported from {args.database} on {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
        " by backend/scripts/export_team_media.py",
        "-- Matched on team slug, because row ids differ between databases. Run it once the",
        "-- fixtures have synced, so the teams it refers to exist. Safe to re-run.",
        "",
    ]
    # Written as a file rather than printed: stadium names carry accents, and a Windows console
    # encodes stdout as cp1252, which cannot represent them.
    path = pathlib.Path(args.out)
    path.write_text("\n".join(header + statements(rows)), encoding="utf-8")
    print(f"{path}: {len(rows)} teams, {photos} with a photo", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
