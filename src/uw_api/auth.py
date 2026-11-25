from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import secrets
import time
from collections.abc import Mapping
from urllib.parse import urljoin, urlparse

import httpx

from uw_api.exceptions import UWAuthError, UWSessionExpiredError

_LOGGER = logging.getLogger(__name__)

_LOGIN_BASE = "https://account.uw.co.uk"
_LOGIN_PAGE = f"{_LOGIN_BASE}/v2/login"
_GRAPHQL_URL = "https://myaccount.uw.co.uk/server/graphql"
_REDIRECT_HOST = "myaccount.uw.co.uk"
_CSRF_COOKIE = "_csrf"
_SESSION_COOKIES = ("uw-user-session", "uw-access-token")
_COOKIE_DOMAIN = ".uw.co.uk"
# Device id baked into every Castle anti-bot token. Shared by all installs:
# one block of this id breaks every user, so callers should pass their own.
_LEGACY_CASTLE_DEVICE_ID = "1ecfa352-d2ed-44fc-8ca3-039196b57897"


def _b64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class UWAuth:
    def __init__(
        self,
        client: httpx.AsyncClient,
        email: str,
        password: str,
        login_page: str = _LOGIN_PAGE,
        graphql_url: str = _GRAPHQL_URL,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        session_cookies: Mapping[str, str] | None = None,
        device_id: str | None = None,
    ) -> None:
        self._client = client
        self._email = email
        self._password = password
        self._login_page = login_page
        self._graphql_url = graphql_url
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        # Per-install device id for the Castle token. Defaults to the legacy
        # shared id for backward compatibility; callers should persist their own.
        self._device_id = device_id or _LEGACY_CASTLE_DEVICE_ID

        self._session_expires_at: float = 0.0
        self._authenticated = False
        self._session_mode = session_cookies is not None
        if session_cookies is not None:
            self._load_session(session_cookies)

    def _load_session(self, cookies: Mapping[str, str]) -> None:
        if not cookies.get(_CSRF_COOKIE):
            raise UWAuthError("Session cookies must include the _csrf cookie")
        if not any(cookies.get(name) for name in _SESSION_COOKIES):
            raise UWAuthError("Session cookies must include one of: " + ", ".join(_SESSION_COOKIES))
        for name, value in cookies.items():
            self._client.cookies.set(name, value, domain=_COOKIE_DOMAIN)
        self._authenticated = True
        self._session_expires_at = float("inf")

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated and time.monotonic() < self._session_expires_at

    @property
    def can_reauthenticate(self) -> bool:
        return not self._session_mode

    @property
    def csrf_token(self) -> str | None:
        return self._client.cookies.get(_CSRF_COOKIE)

    @property
    def graphql_url(self) -> str:
        return self._graphql_url

    def _extract_csrf_token(self, text: str) -> str | None:
        match = re.search(r'<input[^>]+name="_csrf"[^>]+value="([^"]+)"', text)
        if match:
            return match.group(1)
        return None

    def _extract_login_challenge(self, text: str) -> str | None:
        match = re.search(r'name="login_challenge"\s+value="([^"]+)"', text)
        if match:
            return match.group(1)
        match = re.search(r"login_challenge=([a-zA-Z0-9_-]+)", text)
        if match:
            return match.group(1)
        match = re.search(r'"login_challenge":"([^"]+)"', text)
        return match.group(1) if match else None

    def _generate_castle_token(self) -> str:
        payload = {
            "id": self._device_id,
            "type": "device",
            "version": "2.3.0",
            "timestamp": 1753307779,
        }
        encoded = _b64url(json.dumps(payload, separators=(",", ":")).encode())
        return f"eyJhbGciOiJFUzI1NiJ9.{encoded}." + secrets.token_hex(64)

    def _generate_pkce(self) -> tuple[str, str]:
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = _b64url(hashlib.sha256(code_verifier.encode()).digest())
        return code_verifier, code_challenge

    async def _fetch_login_page(self) -> httpx.Response:
        url = "https://myaccount.uw.co.uk/"
        for _ in range(5):
            response = await self._client.get(url)
            if response.status_code == 200:
                return response
            location = response.headers.get("Location", "")
            if not location:
                break
            url = location if location.startswith("http") else urljoin(str(response.url), location)
        raise UWAuthError("Could not reach UW login page")

    async def login(self) -> None:
        if self._session_mode:
            raise UWAuthError(
                "Password login is not available to a session-cookie client; "
                "import fresh cookies instead"
            )
        code_verifier, code_challenge = self._generate_pkce()

        for attempt in range(self._max_retries):
            try:
                login_page = await self._fetch_login_page()
                page_text = login_page.text

                csrf_token = self._extract_csrf_token(page_text)
                login_challenge = self._extract_login_challenge(page_text)

                if not csrf_token:
                    raise UWAuthError("Could not extract CSRF token from login page")
                if not login_challenge:
                    raise UWAuthError("Could not extract login_challenge from login page")

                castle_token = self._generate_castle_token()

                payload = {
                    "_csrf": csrf_token,
                    "login_challenge": login_challenge,
                    "username": self._email,
                    "password": self._password,
                    "castle_request_token": castle_token,
                }

                response = await self._client.post(
                    self._login_page,
                    data=payload,
                    headers={
                        "Referer": self._login_page,
                        "Origin": _LOGIN_BASE,
                    },
                )

                if response.status_code == 429:
                    retry_after = int(
                        response.headers.get("Retry-After", self._backoff_base * (2**attempt))
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code in (401, 403):
                    raise UWAuthError("Invalid credentials")

                if response.is_redirect or response.status_code in (302, 303):
                    await self._follow_redirects(response, code_verifier, code_challenge)
                    self._mark_authenticated()
                    return

                if response.status_code >= 500:
                    await asyncio.sleep(self._backoff_base * (2**attempt))
                    continue

                # An auto-following client (UWClient's own default) has already
                # walked the OAuth redirect chain. A 200 that no longer shows the
                # login form is a completed login; one that does is a rejection.
                if response.status_code == 200 and "login-form" not in response.text:
                    self._mark_authenticated()
                    return

                error = self._extract_error(response.text)
                if error:
                    raise UWAuthError(error)
                raise UWAuthError(f"Unexpected login response: {response.status_code}")

            except UWAuthError:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    retry_after = int(
                        exc.response.headers.get("Retry-After", self._backoff_base * (2**attempt))
                    )
                    await asyncio.sleep(retry_after)
                    continue
                raise UWAuthError(f"Login failed: {exc}") from exc
            except Exception as exc:
                if attempt == self._max_retries - 1:
                    raise UWAuthError(
                        f"Login failed after {self._max_retries} attempts: {exc}"
                    ) from exc
                await asyncio.sleep(self._backoff_base * (2**attempt))

    async def _follow_redirects(
        self,
        response: httpx.Response,
        code_verifier: str,
        code_challenge: str,
    ) -> None:
        location = response.headers.get("Location", "")
        if not location:
            return

        redirect_response = await self._client.get(
            location,
            headers={"Referer": self._login_page},
        )

        final_url = str(redirect_response.url)
        parsed = urlparse(final_url)

        if parsed.hostname and _REDIRECT_HOST in parsed.hostname:
            return

        if redirect_response.is_redirect or redirect_response.status_code in (302, 303):
            await self._follow_redirects(redirect_response, code_verifier, code_challenge)

    def _mark_authenticated(self) -> None:
        if not any(self._client.cookies.get(name) for name in _SESSION_COOKIES):
            raise UWAuthError(
                "Login did not complete — the UW portal did not issue a session cookie"
            )
        self._authenticated = True
        self._session_expires_at = time.monotonic() + 3600

    def _extract_error(self, text: str) -> str | None:
        patterns = [
            r'class="[^"]*error[^"]*"[^>]*>([^<]+)<',
            r"Invalid\s+(?:email|password|credentials)",
            r"login\s+failed",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)
        return None

    async def ensure_authenticated(self) -> None:
        if self.is_authenticated:
            return
        if self._session_mode:
            raise UWSessionExpiredError("UW session cookies have expired; import fresh ones")
        await self.login()

    async def re_auth(self) -> None:
        if self._session_mode:
            raise UWSessionExpiredError("UW session cookies have expired; import fresh ones")
        self._authenticated = False
        await self.login()
