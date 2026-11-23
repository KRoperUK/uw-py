from __future__ import annotations

from typing import Any

from uw_api.graphql import UWGraphQL, register_value


class _StubClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def graphql_request(
        self, operation_name: str, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._payload


def _service(fuel: str, registers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": f"{fuel.lower()}-service",
        "fuelType": fuel,
        "isLive": True,
        "meterpoint": {
            "installedMeter": {
                "id": f"{fuel.lower()}-meter",
                "isSmart": True,
                "serialNumber": "E6S123",
                "reads": {
                    "latestRead": {
                        "id": f"{fuel.lower()}-read",
                        "isEstimated": False,
                        "readDate": "2026-11-01T00:00:00Z",
                        "source": "smart",
                        "registerReading": registers,
                    }
                },
            }
        },
    }


def test_register_value_sums_a_register_list() -> None:
    registers = [{"value": 2404}, {"value": 23863}]
    assert register_value(registers) == 26267


def test_register_value_accepts_a_single_register() -> None:
    assert register_value({"value": 1750}) == 1750


def test_register_value_ignores_missing_values() -> None:
    assert register_value([]) is None
    assert register_value([{"value": None}, {"value": 10}]) == 10
    assert register_value(None) is None


async def test_get_consumption_sums_register_readings() -> None:
    payload = {
        "account": {
            "energy": {
                "services": [
                    _service("ELECTRICITY", [{"value": 2404}, {"value": 23863}]),
                    _service("GAS", [{"value": 900}]),
                ]
            }
        }
    }
    gql = UWGraphQL(_StubClient(payload), http_client=None)  # type: ignore[arg-type]

    consumption = await gql.get_consumption()

    assert consumption is not None
    assert consumption.electricity_kwh == 26267
    assert consumption.gas_kwh == 900


async def test_get_meter_readings_sums_register_readings() -> None:
    payload = {
        "account": {
            "energy": {"services": [_service("ELECTRICITY", [{"value": 10}, {"value": 32}])]}
        }
    }
    gql = UWGraphQL(_StubClient(payload), http_client=None)  # type: ignore[arg-type]

    readings = await gql.get_meter_readings()

    assert len(readings) == 1
    assert readings[0].value == 42
