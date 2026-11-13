"""HTTP client for the SimpleFIN protocol (https://www.simplefin.org/protocol.html).

Flow: the user pastes a base64 *setup token* -> it decodes to a one-time *claim URL* ->
POSTing to it returns a long-lived *access URL* (https://user:pass@host/path) -> we
GET {access_url}/accounts to read balances and transactions.

Pure HTTP: no database access. Called by provider.py. Tests pass a mock `client`.

Every URL is checked against SIMPLEFIN_ALLOWED_HOSTS before any request is made, because setup
tokens and access URLs are pasted by users: without the check, anyone who can sign up could make
the server call arbitrary (e.g. internal) addresses and learn from the error which ones answer.
httpx doesn't follow redirects by default, so an allowed host can't bounce us elsewhere either.
"""

import base64
import binascii
import datetime as dt
import logging
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx

from app.core.clock import to_unix
from app.core.config import get_settings
from app.core.errors import AppError, ProviderAuthError, ProviderError

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(60.0, connect=15.0)
UNREACHABLE = "Couldn't reach SimpleFIN. Please try again in a few minutes."


def check_host(parts: SplitResult) -> None:
    """Allow only https on the default port, to a host in SIMPLEFIN_ALLOWED_HOSTS."""
    host = (parts.hostname or "").lower().rstrip(".")
    try:
        port = parts.port
    except ValueError:  # e.g. "host:abc"
        port = -1
    allowed = get_settings().simplefin_host_list
    if (
        parts.scheme != "https"
        or not host
        or port not in (None, 443)
        or not any(host == d or host.endswith(f".{d}") for d in allowed)
    ):
        raise AppError(
            f"FinTrack only connects to SimpleFIN servers ({', '.join(allowed)}). "
            "To use another one, add its host to SIMPLEFIN_ALLOWED_HOSTS in backend/.env.",
            code="host_not_allowed",
        )


def decode_setup_token(token: str) -> str:
    """Base64-decode a setup token into its claim URL (whitespace and missing padding allowed)."""
    cleaned = "".join(token.split())
    try:
        claim_url = base64.b64decode(cleaned + "=" * (-len(cleaned) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise AppError("That doesn't look like a SimpleFIN setup token.") from exc
    if not claim_url.startswith("https://"):
        raise AppError("That doesn't look like a SimpleFIN setup token.")
    check_host(urlsplit(claim_url))
    return claim_url


def split_access_url(access_url: str) -> tuple[str, tuple[str, str]]:
    """Separate the basic-auth credentials from an access URL."""
    parts = urlsplit(access_url.strip())
    if parts.scheme != "https" or not parts.username or not parts.password or not parts.hostname:
        raise AppError("Invalid SimpleFIN access URL.")
    check_host(parts)
    netloc = parts.hostname + (f":{parts.port}" if parts.port else "")
    base = urlunsplit((parts.scheme, netloc, parts.path.rstrip("/"), "", ""))
    return base, (parts.username, parts.password)


def claim_access_url(setup_token: str, client: httpx.Client | None = None) -> str:
    """Exchange a setup token for an access URL. An access URL pasted directly is accepted too."""
    pasted = setup_token.strip()
    # Handy for SimpleFIN's reusable demo URL, and for moving an existing connection.
    if pasted.startswith("https://") and "@" in pasted:
        split_access_url(pasted)  # validates
        return pasted

    claim_url = decode_setup_token(pasted)
    http = client or httpx.Client(timeout=TIMEOUT)
    try:
        # The claim endpoint expects an empty POST; some servers reject it without this header.
        resp = http.post(claim_url, headers={"Content-Length": "0"})
    except httpx.HTTPError as exc:
        # The details (DNS, refused, TLS...) go to the log only; users see a generic message.
        log.warning("SimpleFIN claim request failed: %s", exc)
        raise ProviderError(UNREACHABLE) from exc
    finally:
        if client is None:
            http.close()

    if resp.status_code == 403:
        raise AppError(
            "SimpleFIN rejected this setup token. It may already have been used; "
            "create a new one in SimpleFIN Bridge."
        )
    if resp.status_code >= 400:
        raise ProviderError(f"SimpleFIN claim failed (HTTP {resp.status_code}).")

    access_url = resp.text.strip()
    split_access_url(access_url)
    return access_url


def fetch_accounts(
    access_url: str,
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """GET /accounts for [start, end]. Credentials go in the Authorization header, not the URL."""
    base, auth = split_access_url(access_url)
    params = {"pending": "1"}  # include pending transactions
    if start:
        params["start-date"] = str(to_unix(start))
    if end:
        params["end-date"] = str(to_unix(end))

    http = client or httpx.Client(timeout=TIMEOUT)
    try:
        resp = http.get(f"{base}/accounts", params=params, auth=auth)
    except httpx.HTTPError as exc:
        log.warning("SimpleFIN accounts request failed: %s", exc)
        raise ProviderError(UNREACHABLE) from exc
    finally:
        if client is None:
            http.close()

    if resp.status_code == 403:
        raise ProviderAuthError(
            "SimpleFIN rejected the stored credentials. The access may have been revoked; "
            "remove this connection and add it again with a new setup token."
        )
    if resp.status_code == 402:
        raise ProviderError("SimpleFIN says payment is required for this account.")
    if resp.status_code >= 400:
        raise ProviderError(f"SimpleFIN request failed (HTTP {resp.status_code}).")
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError("SimpleFIN returned an invalid response.") from exc
