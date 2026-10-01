import httpx
import pytest

from app.database.models import LinkStatus
from app.resolver.resolver import LinkResolver, TooManyRedirectsError
from app.resolver.ssrf import BlockedURLError, URLGuard
from app.validator.validator import LinkValidator


async def public_dns(host, port):
    return ["10.0.0.9"] if host == "internal-rebind.example" else ["93.184.215.14"]


def make_validator(handler, max_redirects=5):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    resolver = LinkResolver(client, URLGuard(resolver=public_dns), max_redirects=max_redirects)
    return LinkValidator(resolver), resolver


def redirect(to, code=302):
    return httpx.Response(code, headers={"location": to})


async def test_follows_redirect_chain_and_meta_refresh():
    def handler(request):
        path = request.url.path
        if path == "/start":
            return redirect("https://hop.example/one", 301)
        if path == "/one":
            return redirect("/two", 307)  # relative Location
        if path == "/two":
            return httpx.Response(200, headers={"content-type": "text/html"},
                                  text='<meta http-equiv="refresh" content="0; url=https://dest.example/watch">')
        if path == "/watch":
            return httpx.Response(200, headers={"content-type": "text/html"}, text="<h1>Live</h1>")
        return httpx.Response(404)

    _, resolver = make_validator(handler)
    result = await resolver.resolve("https://src.example/start")
    assert result.final_url == "https://dest.example/watch"
    assert result.hops == ["https://hop.example/one", "https://hop.example/two", "https://dest.example/watch"]


async def test_redirect_into_private_network_is_blocked_mid_chain():
    def handler(request):
        return redirect("http://169.254.169.254/latest/meta-data/")

    _, resolver = make_validator(handler)
    with pytest.raises(BlockedURLError):
        await resolver.resolve("https://src.example/")


async def test_redirect_to_host_resolving_privately_is_blocked():
    def handler(request):
        return redirect("https://internal-rebind.example/")

    validator, _ = make_validator(handler)
    result = await validator.check("https://src.example/")
    assert result.status == LinkStatus.INVALID and result.error_code == "BLOCKED_BY_POLICY"


async def test_redirect_loop_is_capped():
    def handler(request):
        return redirect("https://loop.example/again")

    _, resolver = make_validator(handler, max_redirects=3)
    with pytest.raises(TooManyRedirectsError):
        await resolver.resolve("https://loop.example/")


@pytest.mark.parametrize(
    ("status", "expected", "code"),
    [
        (200, LinkStatus.VALID, None),
        (404, LinkStatus.INVALID, "HTTP_404"),
        (410, LinkStatus.INVALID, "HTTP_410"),
        (403, LinkStatus.RESOLVED, "HTTP_403"),
        (429, LinkStatus.ERROR, "HTTP_429"),
        (503, LinkStatus.ERROR, "HTTP_503"),
    ],
)
async def test_status_code_mapping(status, expected, code):
    validator, _ = make_validator(lambda r: httpx.Response(status, text="x"))
    result = await validator.check("https://src.example/")
    assert result.status == expected and result.error_code == code


async def test_timeout_is_an_error_not_a_crash():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    validator, _ = make_validator(handler)
    result = await validator.check("https://src.example/")
    assert result.status == LinkStatus.ERROR and result.error_code == "TIMEOUT"


async def test_soft_404_markers_flag_dead_pages():
    validator, _ = make_validator(lambda r: httpx.Response(200, text="<p>Stream is offline</p>"))
    result = await validator.check("https://src.example/", offline_markers=("stream is offline",))
    assert result.status == LinkStatus.INVALID and result.error_code == "NO_LONGER_AVAILABLE"


async def test_geo_redirect_is_unverified_not_working():
    def handler(request):
        if request.url.path == "/unavailable":
            return httpx.Response(200, text="Not available in your region")
        return redirect("https://tv.example/unavailable")

    validator, _ = make_validator(handler)
    result = await validator.check("https://tv.example/sports", geo_block_url_markers=("/unavailable",))
    assert result.status == LinkStatus.RESOLVED and result.error_code == "GEO_RESTRICTED"


async def test_hls_quality_is_only_reported_when_verified():
    manifest = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=1280x720\na.m3u8\n" \
               "#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080\nb.m3u8\n"
    validator, _ = make_validator(
        lambda r: httpx.Response(200, headers={"content-type": "application/vnd.apple.mpegurl"}, text=manifest)
    )
    result = await validator.check("https://cdn.example/master.m3u8")
    assert result.ok and result.verified_quality == "1080p"

    html_validator, _ = make_validator(lambda r: httpx.Response(200, headers={"content-type": "text/html"}, text="hi"))
    assert (await html_validator.check("https://src.example/")).verified_quality is None
