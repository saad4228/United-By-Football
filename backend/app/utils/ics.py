"""Minimal iCalendar (RFC 5545) writer for match reminders and team fixture feeds."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

PRODID = "-//United By Football//Fixtures//EN"
MATCH_LENGTH = timedelta(hours=2)


@dataclass
class CalendarEvent:
    uid: str
    start: datetime
    summary: str
    description: str = ""
    location: str | None = None
    url: str | None = None
    cancelled: bool = False
    alarm_minutes: int | None = None
    end: datetime | None = None


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", ""))


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after a single space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > (75 if not parts else 74):
            parts.append(current.decode("utf-8"))
            current = b""
        current += encoded
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def build_calendar(events: list[CalendarEvent], name: str, now: datetime, refresh_hours: int | None = None) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{_escape(name)}"]
    if refresh_hours:
        # Hints for subscribed feeds; calendar apps decide how often they really refresh.
        lines += [f"REFRESH-INTERVAL;VALUE=DURATION:PT{refresh_hours}H", f"X-PUBLISHED-TTL:PT{refresh_hours}H"]
    for event in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event.uid}",
            f"DTSTAMP:{_stamp(now)}",
            f"DTSTART:{_stamp(event.start)}",
            f"DTEND:{_stamp(event.end or event.start + MATCH_LENGTH)}",
            f"SUMMARY:{_escape(event.summary)}",
        ]
        if event.description:
            lines.append(f"DESCRIPTION:{_escape(event.description)}")
        if event.location:
            lines.append(f"LOCATION:{_escape(event.location)}")
        if event.url:
            lines.append(f"URL:{event.url}")
        if event.cancelled:
            lines.append("STATUS:CANCELLED")
        if event.alarm_minutes:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_escape(event.summary)}",
                      f"TRIGGER:-PT{event.alarm_minutes}M", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
