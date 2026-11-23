from __future__ import annotations

import pytest

from uw_api import UWClient, parse_cookie_string
from uw_api.exceptions import UWAuthError, UWSessionExpiredError

GRAPHQL_URL = "https://myaccount.uw.co.uk/server/graphql"
ACCOUNT_RESPONSE = {
    "data": {
        "account": {
            "id": "acc-uuid-123",
            "number": "12345678",
            "__typename": "Account",
        }
    }
}
SESSION = "_csrf=csrf-value; uw-user-session=session-value; uw_exp_uid=abc"


def test_parse_cookie_string() -> None:
    assert parse_cookie_string(SESSION) == {
        "_csrf": "csrf-value",
        "uw-user-session": "session-value",
        "uw_exp_uid": "abc",
    }


def test_password_client_still_requires_credentials() -> None:
    with pytest.raises(ValueError, match="session_cookies"):
        UWClient()


async def test_session_client_sends_csrf_and_skips_login(httpx_mock) -> None:
    httpx_mock.add_response(method="POST", url=GRAPHQL_URL, json=ACCOUNT_RESPONSE)

    async with UWClient.from_session(SESSION) as client:
        account = await client.gql.get_account()

    assert account.account_number == "12345678"
    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    assert requests[0].headers["x-csrf-token"] == "csrf-value"


async def test_session_requires_csrf_cookie(httpx_mock) -> None:
    async with UWClient.from_session("uw-user-session=session-value") as client:
        with pytest.raises(UWAuthError, match="_csrf"):
            client._ensure_client()


async def test_session_requires_session_cookie(httpx_mock) -> None:
    async with UWClient.from_session("_csrf=csrf-value") as client:
        with pytest.raises(UWAuthError, match="uw-user-session"):
            client._ensure_client()


async def test_expired_session_does_not_attempt_login(httpx_mock) -> None:
    httpx_mock.add_response(method="POST", url=GRAPHQL_URL, status_code=401, json={})

    async with UWClient.from_session(SESSION) as client:
        with pytest.raises(UWSessionExpiredError, match="import fresh"):
            await client.gql.get_account()

    assert len(httpx_mock.get_requests()) == 1


async def test_login_unavailable_in_session_mode(httpx_mock) -> None:
    async with UWClient.from_session(SESSION) as client:
        with pytest.raises(UWAuthError, match="not available"):
            await client.login()
