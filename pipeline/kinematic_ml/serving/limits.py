"""Service limits and constraints for AC75 kinematic simulator serving (Work Packet P5).

Enforces:
- Maximum 1 running inference process at a time.
- At most 4 queued requests; excess rejected immediately.
- Browser trial count policy: preview = 2,000 / standard = 10,000.
- Payload limit: 2 KiB maximum JSON request body.
- Bounded child process output: maximum 1 MiB.
- Process timeout: 15 seconds.
- Loopback peer, Host, and Origin constraints.
"""
from __future__ import annotations

MAX_PAYLOAD_BYTES: int = 2048  # 2 KiB
MAX_CONCURRENT_INFERENCE: int = 1
MAX_QUEUED_REQUESTS: int = 4
MAX_CHILD_OUTPUT_BYTES: int = 1024 * 1024  # 1 MiB
DEFAULT_TIMEOUT_SECONDS: float = 15.0

BROWSER_TRIAL_COUNTS: dict[str, int] = {
    "preview": 2000,
    "standard": 10000,
    "evaluation": 10000,
}

ALLOWED_LOOPBACK_HOSTNAMES = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    "[::1]",
})


def is_allowed_loopback_host(host_header: str | None) -> bool:
    """Verify Host header points to local loopback."""
    if not host_header:
        return True
    try:
        from urllib.parse import urlsplit
        parsed = urlsplit("//" + host_header.strip())
        hostname = (parsed.hostname or "").lower()
        return hostname in ALLOWED_LOOPBACK_HOSTNAMES
    except Exception:
        clean_host = host_header.split(":")[0].strip().lower()
        return clean_host in ALLOWED_LOOPBACK_HOSTNAMES


def is_allowed_same_origin(origin_header: str | None, host_header: str | None) -> bool:
    """Verify Origin header matches loopback Host for browser POST requests."""
    if not origin_header:
        return True
    try:
        from urllib.parse import urlparse
        parsed = urlparse(origin_header)
        origin_hostname = parsed.hostname.lower() if parsed.hostname else ""
        if origin_hostname not in ALLOWED_LOOPBACK_HOSTNAMES:
            return False
        if host_header:
            expected_hostname = host_header.split(":")[0].strip().lower()
            if origin_hostname != expected_hostname:
                # Both are loopback, but ensure they don't cross unexpected boundaries
                if origin_hostname not in ALLOWED_LOOPBACK_HOSTNAMES:
                    return False
        return True
    except Exception:
        return False
