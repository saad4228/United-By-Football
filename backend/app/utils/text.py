import html
import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]*>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
_WS_RE = re.compile(r"\s+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def sanitize_text(value: object, max_length: int = 120) -> str | None:
    """Make third-party text safe to store and render: no markup, no control/bidi
    characters, collapsed whitespace, bounded length."""
    if value is None:
        return None
    text = html.unescape(str(value))
    text = _TAG_RE.sub(" ", text)
    text = _CONTROL_RE.sub("", text)
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return None
    return text[:max_length]


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def slugify(value: str) -> str:
    value = strip_accents(value).lower().replace("&", " and ")
    return _SLUG_RE.sub("-", value).strip("-") or "item"
