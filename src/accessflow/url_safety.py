import ipaddress
import socket
from urllib.parse import urlparse

#One important limitation: this is a good v1 SSRF guard, but it is not
# perfect against DNS rebinding or redirects to private addresses. We should document that later rather than pretending it is production-grade protection.
class UnsafeURLError(ValueError):
    pass


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURLError("Only HTTP and HTTPS URLs are allowed.")

    hostname = parsed.hostname

    if not hostname:
        raise UnsafeURLError("URL must contain a valid hostname.")

    if hostname.lower() == "localhost":
        raise UnsafeURLError("Localhost URLs are not allowed.")

    try:
        addresses = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeURLError("Hostname could not be resolved.") from exc

    for address in addresses:
        ip_text = address[4][0]
        ip = ipaddress.ip_address(ip_text)

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeURLError(
                "URLs resolving to internal or non-public addresses are not allowed."
            )

    return url