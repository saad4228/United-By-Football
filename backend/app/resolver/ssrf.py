"""SSRF guard for every outbound request made on behalf of a discovered link.

Blocks non-HTTP schemes, embedded credentials, unexpected ports, and any host that
resolves to loopback, private, link-local (incl. cloud metadata 169.254.169.254),
CGNAT, multicast or otherwise non-global address space. Each redirect hop is
re-checked, and the connected peer address is verified after connect to narrow
the DNS-rebinding window. Production deployments should still run the checker
with an egress firewall that denies internal ranges.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx

Resolver = Callable[[str, int], Awaitable[list[str]]]

_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa", ".intranet", ".corp")
_BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal"}


class URLPolicyError(Exception):
    """The URL is not allowed by policy (never fetched)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class InvalidURLError(URLPolicyError):
    def __init__(self, message: str):
        super().__init__("INVALID_URL", message)


class BlockedURLError(URLPolicyError):
    def __init__(self, message: str):
        super().__init__("BLOCKED_BY_POLICY", message)


class DNSResolutionError(URLPolicyError):
    def __init__(self, message: str):
        super().__init__("DNS_ERROR", message)


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list({info[4][0] for info in infos})


def is_public_ip(raw: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = ip.ipv4_mapped or ip.sixtofour or (ip.teredo[1] if ip.teredo else None)
        if embedded is not None and not is_public_ip(str(embedded)):
            return False
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local)


def parse_http_url(url: str) -> tuple[str, str, int]:
    """Validate shape and return (scheme, host, port). Raises InvalidURLError."""
    if not isinstance(url, str) or len(url) > 2048:
        raise InvalidURLError("URL missing or too long")
    if any(ch.isspace() or ord(ch) < 0x20 for ch in url):
        raise InvalidURLError("URL contains whitespace or control characters")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise InvalidURLError(f"Unparseable URL: {exc}") from exc
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise InvalidURLError(f"Scheme {scheme or '(none)'} is not allowed")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise InvalidURLError("Credentials in URLs are not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise InvalidURLError("URL has no host")
    try:
        host = host.encode("idna").decode("ascii") if not host.isascii() else host
    except UnicodeError as exc:
        raise InvalidURLError("Invalid international domain name") from exc
    return scheme, host, port or (443 if scheme == "https" else 80)


class URLGuard:
    def __init__(
        self,
        allowed_ports: set[int] | None = None,
        allow_hosts: set[str] | None = None,
        resolver: Resolver = system_resolver,
    ):
        self.allowed_ports = allowed_ports or {80, 443}
        self.allow_hosts = {h.lower() for h in (allow_hosts or set())}
        self.resolver = resolver

    def is_exempt(self, host: str, port: int) -> bool:
        return f"{host}:{port}" in self.allow_hosts or host in self.allow_hosts

    async def check(self, url: str) -> None:
        _, host, port = parse_http_url(url)
        if self.is_exempt(host, port):
            return
        if port not in self.allowed_ports:
            raise BlockedURLError(f"Port {port} is not allowed")
        if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES):
            raise BlockedURLError(f"Host {host} is internal")
        literal = host.strip("[]")
        try:
            ipaddress.ip_address(literal)
            addresses = [literal]
        except ValueError:
            try:
                addresses = await self.resolver(host, port)
            except (OSError, UnicodeError) as exc:
                raise DNSResolutionError(f"Could not resolve {host}: {exc}") from exc
        if not addresses:
            raise DNSResolutionError(f"No addresses for {host}")
        for address in addresses:
            if not is_public_ip(address):
                raise BlockedURLError(f"{host} resolves to non-public address {address}")

    def check_peer(self, response: httpx.Response) -> None:
        """Reject responses that came from a non-public peer (DNS rebinding)."""
        try:
            _, host, port = parse_http_url(str(response.request.url))
        except InvalidURLError:
            return
        if self.is_exempt(host, port):
            return
        stream = response.extensions.get("network_stream")
        if stream is None:
            return
        addr = stream.get_extra_info("server_addr")
        if addr and not is_public_ip(str(addr[0])):
            raise BlockedURLError(f"Connected peer {addr[0]} is not a public address")
