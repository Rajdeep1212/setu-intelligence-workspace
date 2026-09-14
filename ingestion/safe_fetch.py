"""Conservative HTTP fetcher with allowlist, redirect, and SSRF controls."""

from __future__ import annotations

import email.utils
import ipaddress
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable
from urllib.parse import urljoin, urlsplit

import requests


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/octet-stream",
    "text/html",
    "application/xhtml+xml",
    "text/plain",
}


class FetchError(RuntimeError):
    retry_eligible = False


class RetryableFetchError(FetchError):
    retry_eligible = True

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class UnsafeUrlError(FetchError):
    pass


class ResponseLimitError(FetchError):
    pass


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    status_code: int
    content_type: str
    content: bytes
    etag: str | None
    last_modified: str | None


Resolver = Callable[..., Iterable[tuple]]


class SafeHttpFetcher:
    def __init__(
        self,
        allowed_hosts: Iterable[str],
        *,
        session: requests.Session | None = None,
        resolver: Resolver = socket.getaddrinfo,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        max_bytes: int = 12 * 1024 * 1024,
        max_redirects: int = 5,
        retries: int = 2,
        min_host_interval: float = 1.0,
        max_retry_after: float = 30.0,
    ) -> None:
        self.allowed_hosts = {host.casefold().rstrip(".") for host in allowed_hosts}
        if not self.allowed_hosts:
            raise ValueError("allowed_hosts cannot be empty")
        self.session = session or requests.Session()
        self.resolver = resolver
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.retries = retries
        self.min_host_interval = min_host_interval
        self.max_retry_after = max_retry_after
        self._last_request_by_host: dict[str, float] = {}

    def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9",
            "User-Agent": "SETU-Corpus-Research/1.0 (bounded official-source fetch)",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        last_error: BaseException | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._fetch_with_redirects(url, headers)
            except RetryableFetchError as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                delay = exc.retry_after if exc.retry_after is not None else 1.5 * (attempt + 1)
                time.sleep(min(max(delay, 0.0), self.max_retry_after))
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(1.5 * (attempt + 1))
        raise RetryableFetchError(
            f"Request failed after {self.retries + 1} attempts: {last_error}"
        ) from last_error

    def _fetch_with_redirects(self, original_url: str, headers: dict[str, str]) -> FetchResult:
        current_url = original_url
        for redirect_count in range(self.max_redirects + 1):
            host = self._validate_url(current_url)
            self._respect_host_interval(host)
            response = self.session.get(
                current_url,
                allow_redirects=False,
                headers=headers,
                stream=True,
                timeout=(self.connect_timeout, self.read_timeout),
            )
            if response.status_code in REDIRECT_STATUS_CODES:
                response.close()
                if redirect_count >= self.max_redirects:
                    raise FetchError(f"Too many redirects for {original_url}")
                location = response.headers.get("Location")
                if not location:
                    raise FetchError("Redirect response did not include Location")
                current_url = urljoin(current_url, location)
                continue
            if response.status_code in RETRYABLE_STATUS_CODES:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                response.close()
                raise RetryableFetchError(
                    f"Official source returned HTTP {response.status_code}", retry_after
                )
            if response.status_code == 304:
                response.close()
                return FetchResult(current_url, 304, "", b"", None, None)
            if not 200 <= response.status_code < 300:
                response.close()
                raise FetchError(
                    f"Official source returned non-retryable HTTP {response.status_code}"
                )
            try:
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].casefold()
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > self.max_bytes:
                    raise ResponseLimitError(
                        f"Content-Length {content_length} exceeds {self.max_bytes} bytes"
                    )
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ResponseLimitError(
                            f"Response exceeded {self.max_bytes} bytes while streaming"
                        )
                    chunks.append(chunk)
                content = b"".join(chunks)
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise FetchError(f"Unsupported Content-Type: {content_type or 'missing'}")
                if content_type == "application/octet-stream" and not (
                    current_url.casefold().endswith(".pdf") or content.startswith(b"%PDF-")
                ):
                    raise FetchError("Generic binary response is not an identifiable PDF")
                return FetchResult(
                    final_url=current_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    content=content,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                )
            finally:
                response.close()
        raise FetchError(f"Redirect processing failed for {original_url}")

    def _validate_url(self, url: str) -> str:
        parsed = urlsplit(url)
        if parsed.scheme.casefold() != "https":
            raise UnsafeUrlError("Only HTTPS official sources are allowed")
        if parsed.username or parsed.password or parsed.fragment:
            raise UnsafeUrlError("Credentials and fragments are not allowed in source URLs")
        if parsed.port not in (None, 443):
            raise UnsafeUrlError("Non-standard URL ports are not allowed")
        if not parsed.hostname:
            raise UnsafeUrlError("Source URL has no hostname")
        host = parsed.hostname.encode("idna").decode("ascii").casefold().rstrip(".")
        if host not in self.allowed_hosts:
            raise UnsafeUrlError(f"Host is not in the exact allowlist: {host}")
        try:
            addresses = self.resolver(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise RetryableFetchError(f"DNS resolution failed for {host}: {exc}") from exc
        resolved = {entry[4][0].split("%", 1)[0] for entry in addresses}
        if not resolved:
            raise RetryableFetchError(f"DNS returned no addresses for {host}")
        for address in resolved:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise UnsafeUrlError(
                    f"Host {host} resolved to prohibited non-global address {address}"
                )
        return host

    def _respect_host_interval(self, host: str) -> None:
        previous = self._last_request_by_host.get(host)
        if previous is not None:
            remaining = self.min_host_interval - (time.monotonic() - previous)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_by_host[host] = time.monotonic()


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    stripped = value.strip()
    if stripped.isdigit():
        return float(stripped)
    try:
        parsed = email.utils.parsedate_to_datetime(stripped)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None
