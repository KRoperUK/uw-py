from __future__ import annotations

import httpx
import pytest

from uw_api.auth import UWAuth
from uw_api.exceptions import UWAuthError

CHALLENGE = "challenge-abc"
CSRF = "csrf-xyz"
LOGIN_PAGE_URL = "https://account.uw.co.uk/v2/login"
CALLBACK_URL = "https://myaccount.uw.co.uk/login/callback?code=one-time-code"
INVALID_CREDENTIALS = "Oops, invalid credentials. Please try again."


def _login_html(*, error: str | None = None) -> str:
    error_markup = f'<div class="form__error">{error}</div>' if error else ""
    return (
        "<html><body>"
        '<form id="login-form" name="login-form" method="POST" action="/v2/login">'
        f'<input type="hidden" name="login_challenge" value="{CHALLENGE}" />'
        f'<input type="hidden" name="_csrf" value="{CSRF}" />'
        "</form>"
        f"{error_markup}"
        "</body></html>"
    )


def _register_login_page(httpx_mock, *, login_html: str) -> None:
    httpx_mock.add_response(
        url="https://myaccount.uw.co.uk/",
        status_code=302,
        headers={"Location": "/login"},
    )
    httpx_mock.add_response(
        url="https://myaccount.uw.co.uk/login",
        status_code=302,
        headers={"Location": f"{LOGIN_PAGE_URL}?login_challenge={CHALLENGE}"},
    )
    httpx_mock.add_response(
        url=f"{LOGIN_PAGE_URL}?login_challenge={CHALLENGE}",
        status_code=200,
        text=login_html,
    )


def _register_successful_submit(httpx_mock, *, session_cookie: bool = True) -> None:
    httpx_mock.add_response(
        method="POST",
        url=LOGIN_PAGE_URL,
        status_code=302,
        headers={"Location": CALLBACK_URL},
    )
    headers = {"set-cookie": "uw-access-token=session-token; Path=/"} if session_cookie else {}
    httpx_mock.add_response(
        url=CALLBACK_URL,
        status_code=200,
        text="<html>dashboard</html>",
        headers=headers,
    )


def _auth(client: httpx.AsyncClient) -> UWAuth:
    return UWAuth(client, email="user@example.com", password="secret")


class TestLogin:
    async def test_success_when_client_follows_redirects(self, httpx_mock) -> None:
        _register_login_page(httpx_mock, login_html=_login_html())
        _register_successful_submit(httpx_mock)
        async with httpx.AsyncClient(follow_redirects=True) as http:
            auth = _auth(http)
            await auth.login()
            assert auth.is_authenticated

    async def test_success_when_client_does_not_follow_redirects(self, httpx_mock) -> None:
        _register_login_page(httpx_mock, login_html=_login_html())
        _register_successful_submit(httpx_mock)
        async with httpx.AsyncClient(follow_redirects=False) as http:
            auth = _auth(http)
            await auth.login()
            assert auth.is_authenticated

    async def test_rejected_credentials_surface_portal_message(self, httpx_mock) -> None:
        rejected = _login_html(error=INVALID_CREDENTIALS)
        _register_login_page(httpx_mock, login_html=_login_html())
        httpx_mock.add_response(method="POST", url=LOGIN_PAGE_URL, status_code=200, text=rejected)
        async with httpx.AsyncClient(follow_redirects=True) as http:
            auth = _auth(http)
            with pytest.raises(UWAuthError, match="invalid credentials"):
                await auth.login()

    async def test_missing_session_cookie_is_not_success(self, httpx_mock) -> None:
        _register_login_page(httpx_mock, login_html=_login_html())
        _register_successful_submit(httpx_mock, session_cookie=False)
        async with httpx.AsyncClient(follow_redirects=True) as http:
            auth = _auth(http)
            with pytest.raises(UWAuthError, match="session cookie"):
                await auth.login()

    async def test_missing_csrf_raises(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="https://myaccount.uw.co.uk/", status_code=200, text="<html></html>"
        )
        async with httpx.AsyncClient(follow_redirects=True) as http:
            auth = _auth(http)
            with pytest.raises(UWAuthError, match="CSRF"):
                await auth.login()
