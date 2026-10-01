"""Link resolution: follow ordinary redirects to the real destination.

Handles HTTP 301/302/303/307/308 and <meta http-equiv="refresh"> hops. Every hop
passes through the SSRF guard. Nothing here executes scripts, solves challenges,
or replays credentials — pages that require any of that are reported as-is.
"""

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx

from app.resolver.ssrf import InvalidURLError, URLGuard

REDIRECT_CODES = {301, 302, 303, 307, 308}
_META_REFRESH = re.compile(
    rb"""<meta[^>]+http-equiv\s*=\s*["']?refresh["']?[^>]*content\s*=\s*["']?\s*(\d+)\s*;\s*url\s*=\s*([^"'>\s]+)""",
    re.IGNORECASE,
)
MAX_META_REFRESH_DELAY = 10


class TooManyRedirectsError(Exception):
    pass


@dataclass
class ResolvedResponse:
    original_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    elapsed_ms: int
    hops: list[str] = field(default_factory=list)


def find_meta_refresh(body: bytes) -> str | None:
    match = _META_REFRESH.search(body)
    if not match or int(match.group(1)) > MAX_META_REFRESH_DELAY:
        return None
    return match.group(2).decode("utf-8", "ignore").strip()


class LinkResolver:
    def __init__(self, client: httpx.AsyncClient, guard: URLGuard, max_redirects: int = 5, max_body: int = 65_536):
        self.client = client
        self.guard = guard
        self.max_redirects = max_redirects
        self.max_body = max_body

    async def resolve(self, url: str) -> ResolvedResponse:
        current = url
        hops: list[str] = []
        started = time.perf_counter()
        for _ in range(self.max_redirects + 1):
            await self.guard.check(current)
            async with self.client.stream("GET", current, follow_redirects=False) as response:
                self.guard.check_peer(response)
                location = response.headers.get("location")
                if response.status_code in REDIRECT_CODES and location:
                    current = self._next(str(response.url), location)
                    hops.append(current)
                    continue
                body = await self._read_limited(response)
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if 200 <= response.status_code < 300 and content_type in ("text/html", "application/xhtml+xml"):
                    refresh = find_meta_refresh(body)
                    if refresh:
                        current = self._next(str(response.url), refresh)
                        hops.append(current)
                        continue
                return ResolvedResponse(
                    original_url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    body=body,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                    hops=hops,
                )
        raise TooManyRedirectsError(f"More than {self.max_redirects} redirects")

    @staticmethod
    def _next(base: str, location: str) -> str:
        target = urljoin(base, location.strip())
        if not target.lower().startswith(("http://", "https://")):
            raise InvalidURLError("Redirect to a non-HTTP destination")
        return target

    async def _read_limited(self, response: httpx.Response) -> bytes:
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            chunks.append(chunk)
            size += len(chunk)
            if size >= self.max_body:
                break
        return b"".join(chunks)[: self.max_body]
