from __future__ import annotations

import time

import pytest

from uw_api.client import UWClient


@pytest.fixture
def graphql_account() -> dict:
    return {
        "data": {
            "account": {
                "id": "acc-uuid-123",
                "number": "12345678",
                "__typename": "Account",
            }
        }
    }


@pytest.fixture
def graphql_bills() -> dict:
    return {
        "data": {
            "customerBilling": {
                "id": "bill-uuid",
                "accountBills": {
                    "billsList": [
                        {
                            "invoiceId": "INV-001",
                            "invoiceDate": {
                                "seconds": 1735689600,
                                "nanos": 0,
                                "__typename": "Timestamp",
                            },
                            "total": {
                                "value": "120.50",
                                "currency": "GBP",
                                "__typename": "Money",
                            },
                            "url": "https://cdn.example.com/bill.pdf",
                            "__typename": "Bill",
                        }
                    ],
                    "__typename": "AccountBills",
                },
                "__typename": "CustomerBilling",
            }
        }
    }


def _mock_authenticated(client: UWClient) -> None:
    client._ensure_client()
    assert client._auth_obj is not None
    client._auth_obj._authenticated = True
    client._auth_obj._session_expires_at = time.monotonic() + 3600


class TestGraphQL:
    async def test_get_account(self, httpx_mock, graphql_account: dict) -> None:
        httpx_mock.add_response(
            method="POST",
            url="https://myaccount.uw.co.uk/server/graphql",
            json=graphql_account,
            status_code=200,
        )

        async with UWClient(email="test@example.com", password="secret") as client:
            _mock_authenticated(client)
            account = await client.gql.get_account()
            assert account.account_id == "acc-uuid-123"
            assert account.account_number == "12345678"

    async def test_get_bills(self, httpx_mock, graphql_bills: dict) -> None:
        httpx_mock.add_response(
            method="POST",
            url="https://myaccount.uw.co.uk/server/graphql",
            json=graphql_bills,
            status_code=200,
        )

        async with UWClient(email="test@example.com", password="secret") as client:
            _mock_authenticated(client)
            bills = await client.gql.get_bills()
            assert len(bills) == 1
            assert bills[0].bill_id == "INV-001"
            assert bills[0].total_amount_gbp == 120.50
            assert bills[0].pdf is not None
            assert bills[0].pdf.pdf_url == "https://cdn.example.com/bill.pdf"

    async def test_empty_bills(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST",
            url="https://myaccount.uw.co.uk/server/graphql",
            json={"data": {"customerBilling": {"accountBills": {"billsList": []}}}},
            status_code=200,
        )

        async with UWClient(email="test@example.com", password="secret") as client:
            _mock_authenticated(client)
            bills = await client.gql.get_bills()
            assert bills == []
