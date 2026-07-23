from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import secrets
import time
from urllib.parse import urlparse

import httpx

from uw_api.exceptions import UWAuthError

_LOGGER = logging.getLogger(__name__)

_LOGIN_BASE = "https://account.uw.co.uk"
_LOGIN_PAGE = f"{_LOGIN_BASE}/v2/login"
_GRAPHQL_URL = "https://myaccount.uw.co.uk/server/graphql"
_REDIRECT_HOST = "myaccount.uw.co.uk"


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
    ) -> None:
        self._client = client
        self._email = email
        self._password = password
        self._login_page = login_page
        self._graphql_url = graphql_url
        self._max_retries = max_retries
        self._backoff_base = backoff_base

        self._session_expires_at: float = 0.0
        self._authenticated = False

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated and time.monotonic() < self._session_expires_at

    @property
    def csrf_token(self) -> str | None:
        return None

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
        return (
            "eyJhbGciOiJFUzI1NiJ9.eyJpZCI6IjFlY2ZhMzUyLWQyZWQtNDRm"
            "Yy04Y2EzLTAzOTE5NmI1Nzg5NyIsInR5cGUiOiJkZXZpY2UiLCJ2ZXJ"
            "zaW9uIjoiMi4zLjAiLCJ0aW1lc3RhbXAiOjE3NTMzMDc3Nzl9." + secrets.token_hex(64)
        )

    def _generate_pkce(self) -> tuple[str, str]:
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = _b64url(hashlib.sha256(code_verifier.encode()).digest())
        return code_verifier, code_challenge

    async def _fetch_login_page(self) -> httpx.Response:
        response = await self._client.get(self._login_page)
        response.raise_for_status()
        return response

    async def login(self) -> None:
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
                    self._authenticated = True
                    self._session_expires_at = time.monotonic() + 3600
                    return

                if response.status_code >= 500:
                    await asyncio.sleep(self._backoff_base * (2**attempt))
                    continue

                page_text = response.text
                error = self._extract_error(page_text)
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
        if not self.is_authenticated:
            await self.login()

    async def re_auth(self) -> None:
        self._authenticated = False
        await self.login()
