import pytest

from app.resolver.ssrf import BlockedURLError, DNSResolutionError, InvalidURLError, URLGuard, is_public_ip


def guard(addresses):
    async def resolver(host, port):
        return addresses

    return URLGuard(resolver=resolver)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/admin",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://100.64.0.1/",
        "http://0.0.0.0/",
        "http://service.internal/",
        "http://example.com:6379/",
    ],
)
async def test_internal_destinations_are_blocked(url):
    with pytest.raises(BlockedURLError):
        await guard(["93.184.215.14"]).check(url)


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "gopher://x/", "javascript:alert(1)", "http://user:pw@example.com/", "http://", "ftp://a/"],
)
async def test_malformed_or_non_http_urls_are_rejected(url):
    with pytest.raises(InvalidURLError):
        await guard(["93.184.215.14"]).check(url)


async def test_hostname_resolving_to_private_address_is_blocked():
    with pytest.raises(BlockedURLError):
        await guard(["10.1.2.3"]).check("https://rebind.example.com/")


async def test_any_private_address_in_the_answer_blocks():
    with pytest.raises(BlockedURLError):
        await guard(["93.184.215.14", "127.0.0.1"]).check("https://mixed.example.com/")


async def test_public_destination_is_allowed():
    await guard(["93.184.215.14"]).check("https://example.com/watch?x=1")


async def test_dns_failure_is_reported():
    async def failing(host, port):
        raise OSError("nxdomain")

    with pytest.raises(DNSResolutionError):
        await URLGuard(resolver=failing).check("https://nope.example/")


async def test_explicit_allow_list_is_exact_host_and_port():
    g = URLGuard(allow_hosts={"127.0.0.1:8000"})
    await g.check("http://127.0.0.1:8000/mock-sources/listing")
    with pytest.raises(BlockedURLError):
        await g.check("http://127.0.0.1:8001/")


def test_public_ip_helper():
    assert is_public_ip("8.8.8.8")
    assert not is_public_ip("172.16.0.1")
    assert not is_public_ip("fe80::1")
    assert not is_public_ip("2002:7f00:1::")  # 6to4 wrapping 127.0.0.1
