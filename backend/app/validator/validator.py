"""Link validation: is the resolved destination actually reachable right now?"""

import re
from dataclasses import dataclass

import httpx

from app.database.models import LinkStatus
from app.resolver.resolver import LinkResolver, TooManyRedirectsError
from app.resolver.ssrf import URLPolicyError

HLS_TYPES = {"application/vnd.apple.mpegurl", "application/x-mpegurl", "audio/mpegurl"}
_RESOLUTION = re.compile(rb"RESOLUTION=\d+x(\d+)")


def hls_quality(body: bytes) -> str | None:
    """Highest rendition advertised by an HLS master playlist — the only quality we can verify."""
    heights = [int(h) for h in _RESOLUTION.findall(body)]
    return f"{max(heights)}p" if heights else None


@dataclass
class CheckResult:
    status: LinkStatus
    error_code: str | None = None
    http_status: int | None = None
    final_url: str | None = None
    hops: int = 0
    response_time_ms: int | None = None
    verified_quality: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == LinkStatus.VALID


class LinkValidator:
    def __init__(self, resolver: LinkResolver):
        self.resolver = resolver

    async def check(
        self,
        url: str,
        offline_markers: tuple[str, ...] = (),
        geo_block_url_markers: tuple[str, ...] = (),
    ) -> CheckResult:
        try:
            res = await self.resolver.resolve(url)
        except URLPolicyError as exc:
            status = LinkStatus.ERROR if exc.code == "DNS_ERROR" else LinkStatus.INVALID
            return CheckResult(status, exc.code)
        except TooManyRedirectsError:
            return CheckResult(LinkStatus.INVALID, "TOO_MANY_REDIRECTS")
        except httpx.TimeoutException:
            return CheckResult(LinkStatus.ERROR, "TIMEOUT")
        except httpx.HTTPError:
            return CheckResult(LinkStatus.ERROR, "CONNECTION_ERROR")

        base = dict(http_status=res.status_code, final_url=res.final_url, hops=len(res.hops),
                    response_time_ms=res.elapsed_ms)
        code = res.status_code
        final = res.final_url.lower()
        if geo_block_url_markers and any(marker in final for marker in geo_block_url_markers):
            return CheckResult(LinkStatus.RESOLVED, "GEO_RESTRICTED", **base)
        if 200 <= code < 300:
            # Soft-404s: a 200 page whose body says the content is gone. Markers are supplied
            # per connector, because generic phrases appear in many sites' inline scripts.
            text = res.body.decode("utf-8", "ignore").lower() if offline_markers else ""
            if any(marker in text for marker in offline_markers):
                return CheckResult(LinkStatus.INVALID, "NO_LONGER_AVAILABLE", **base)
            quality = hls_quality(res.body) if res.content_type in HLS_TYPES else None
            return CheckResult(LinkStatus.VALID, None, verified_quality=quality, **base)
        if code in (401, 403):
            # Reachable but access-controlled (login, geo or bot protection). We never try to
            # get around that, so the honest state is "resolved, not verified".
            return CheckResult(LinkStatus.RESOLVED, f"HTTP_{code}", **base)
        if code in (404, 410):
            return CheckResult(LinkStatus.INVALID, f"HTTP_{code}", **base)
        if code == 429:
            return CheckResult(LinkStatus.ERROR, "HTTP_429", **base)
        return CheckResult(LinkStatus.ERROR, f"HTTP_{code}", **base)
