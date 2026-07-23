from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from uw_api.auth import UWAuth
from uw_api.exceptions import UWApiError, UWRateLimitError
from uw_api.graphql import UWGraphQL

_LOGGER = logging.getLogger(__name__)


class UWClient:
    def __init__(
        self,
        email: str,
        password: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> None:
        self._email = email
        self._password = password
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base

        self._http_client = httpx.AsyncClient(
            http2=False,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

        self._auth = UWAuth(
            self._http_client,
            email=self._email,
            password=self._password,
            max_retries=max_retries,
            backoff_base=backoff_base,
        )

        self.gql = UWGraphQL(self, self._http_client)

    @property
    def http_client(self) -> httpx.AsyncClient:
        return self._http_client

    async def login(self) -> None:
        await self._auth.login()

    async def close(self) -> None:
        await self._http_client.aclose()

    async def __aenter__(self) -> UWClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def graphql_request(
        self,
        operation_name: str,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self._auth.ensure_authenticated()

        body: dict[str, Any] = {
            "operationName": operation_name,
            "query": query,
            "variables": variables or {},
        }

        for attempt in range(self._max_retries):
            try:
                response = await self._http_client.post(
                    self._auth.graphql_url,
                    json=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-csrf-token": self._auth.csrf_token or "1",
                    },
                )

                if response.status_code == 401:
                    _LOGGER.warning("Session expired, re-authenticating")
                    await self._auth.re_auth()
                    continue

                if response.status_code == 429:
                    retry_after = int(
                        response.headers.get(
                            "Retry-After",
                            self._backoff_base * (2**attempt),
                        )
                    )
                    if attempt == self._max_retries - 1:
                        raise UWRateLimitError(f"Rate limited. Retry after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code >= 500:
                    await asyncio.sleep(self._backoff_base * (2**attempt))
                    continue

                response.raise_for_status()
                raw: object = response.json()
                if not isinstance(raw, dict):
                    raise UWApiError(f"Unexpected response type: {type(raw)}")
                data: dict[str, Any] = raw

                errors = data.get("errors")
                if errors:
                    raise UWApiError(f"GraphQL errors: {errors}")

                result = data.get("data", data)
                if not isinstance(result, dict):
                    raise UWApiError(f"Unexpected data key type: {type(result)}")
                return result

            except (UWRateLimitError, UWApiError):
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    _LOGGER.warning("Session expired, re-authenticating")
                    await self._auth.re_auth()
                    continue
                if exc.response.status_code == 429:
                    retry_after = int(
                        exc.response.headers.get(
                            "Retry-After",
                            self._backoff_base * (2**attempt),
                        )
                    )
                    if attempt == self._max_retries - 1:
                        raise UWRateLimitError(f"Rate limited. Retry after {retry_after}s") from exc
                    await asyncio.sleep(retry_after)
                    continue
                raise UWApiError(f"HTTP {exc.response.status_code}: {exc}") from exc
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                if attempt == self._max_retries - 1:
                    raise UWApiError(f"Request failed: {exc}") from exc
                await asyncio.sleep(self._backoff_base * (2**attempt))

        raise UWApiError(f"Request failed after {self._max_retries} attempts")
