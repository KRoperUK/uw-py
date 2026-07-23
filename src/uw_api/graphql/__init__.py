from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from uw_api.graphql.queries import (
    GET_ACCOUNT,
    GET_BALANCE,
    GET_BILLS,
    GET_ENERGY_SERVICES,
    GET_EV_TARIFF,
    GET_LIVE_SERVICES,
    GET_PDF_URL,
)
from uw_api.models.account import UWAccount
from uw_api.models.bill import Bill, BillPDFMetadata, BillStatus
from uw_api.models.energy import EnergyConsumption, EnergyTariff, EnergyUsage, UsageReading
from uw_api.models.meter import Meter, MeterReading, MeterType

if TYPE_CHECKING:
    from uw_api.client import UWClient


class UWGraphQL:
    def __init__(self, client: UWClient, http_client: httpx.AsyncClient) -> None:
        self._client = client
        self._http_client = http_client

    async def get_account(self) -> UWAccount:
        data = await self._client.graphql_request("GetAccount", GET_ACCOUNT)
        account = data["account"]
        return UWAccount(
            account_id=account["id"],
            account_number=account["number"],
            email=self._client._email,
        )

    async def get_energy_services(self) -> list[dict[str, Any]]:
        data = await self._client.graphql_request(
            "accountEnergyServicesWithReads",
            GET_ENERGY_SERVICES,
            {"includeEndedWithin": 108000},
        )
        return list(data.get("account", {}).get("energy", {}).get("services", []))

    async def get_energy_usage(self) -> list[EnergyUsage]:
        services = await self.get_energy_services()
        results: list[EnergyUsage] = []
        for svc in services:
            meter = svc.get("meterpoint", {}).get("installedMeter", {})
            reads_data = meter.get("reads", {})
            latest = reads_data.get("latestRead")
            readings: list[UsageReading] = []
            total_kwh: float = 0.0

            if latest:
                rr = latest.get("registerReading", {})
                if rr:
                    read_date = latest.get("readDate", "")
                    dt = (
                        datetime.fromisoformat(read_date.replace("Z", "+00:00"))
                        if read_date
                        else datetime.now(tz=UTC)
                    )
                    val = float(rr.get("value", 0))
                    readings.append(
                        UsageReading(
                            date=dt,
                            value=val,
                            unit="kWh",
                            reading_type=("estimated" if latest.get("isEstimated") else "actual"),
                        )
                    )
                    total_kwh = val

            results.append(
                EnergyUsage(
                    service_id=svc.get("id", ""),
                    meter_number=meter.get("serialNumber", ""),
                    readings=readings,
                    total_consumption_kwh=total_kwh,
                )
            )
        return results

    async def get_consumption(self) -> EnergyConsumption | None:
        services = await self.get_energy_services()
        if not services:
            return None

        elec_kwh: float | None = None
        gas_kwh: float | None = None

        for svc in services:
            fuel = svc.get("fuelType", "").upper()
            meter = svc.get("meterpoint", {}).get("installedMeter", {})
            latest = meter.get("reads", {}).get("latestRead", {})
            rr = latest.get("registerReading", {})
            val = float(rr.get("value", 0)) if rr.get("value") else 0.0

            if fuel == "ELECTRICITY":
                elec_kwh = val
            elif fuel == "GAS":
                gas_kwh = val

        return EnergyConsumption(
            service_id=services[0].get("id", ""),
            period="latest",
            electricity_kwh=elec_kwh,
            gas_kwh=gas_kwh,
        )

    async def get_meters(self) -> list[Meter]:
        services = await self.get_energy_services()
        results: list[Meter] = []
        for svc in services:
            fuel = svc.get("fuelType", "").upper()
            meter = svc.get("meterpoint", {}).get("installedMeter", {})
            serial = meter.get("serialNumber", "")

            meter_type = MeterType.ELECTRICITY if fuel == "ELECTRICITY" else MeterType.GAS

            latest = meter.get("reads", {}).get("latestRead", {})
            read_date_str = latest.get("readDate")
            read_date = None
            if read_date_str:
                read_date = datetime.fromisoformat(read_date_str.replace("Z", "+00:00"))

            results.append(
                Meter(
                    meter_id=meter.get("id", ""),
                    service_id=svc.get("id", ""),
                    meter_type=meter_type,
                    meter_number=serial,
                    is_smart=meter.get("isSmart", False),
                    last_reading_date=read_date,
                )
            )
        return results

    async def get_meter_readings(self) -> list[MeterReading]:
        services = await self.get_energy_services()
        results: list[MeterReading] = []
        for svc in services:
            meter = svc.get("meterpoint", {}).get("installedMeter", {})
            latest = meter.get("reads", {}).get("latestRead", {})
            actual_read = meter.get("reads", {}).get("latestActualRead", {})

            for read in [latest, actual_read]:
                if not read or not read.get("id"):
                    continue
                rr = read.get("registerReading", {})
                if not rr.get("value"):
                    continue
                read_date_str = read.get("readDate", "")
                read_date = (
                    datetime.fromisoformat(read_date_str.replace("Z", "+00:00"))
                    if read_date_str
                    else datetime.now(tz=UTC)
                )

                results.append(
                    MeterReading(
                        reading_id=read.get("id"),
                        meter_id=meter.get("id", ""),
                        reading_date=read_date,
                        value=float(rr.get("value", 0)),
                        unit="kWh",
                        reading_type=("estimated" if read.get("isEstimated") else "actual"),
                        source=read.get("source", "customer"),
                    )
                )
        return results

    async def get_tariff(self) -> EnergyTariff | None:
        data = await self._client.graphql_request("accountServicesEvTariff", GET_EV_TARIFF)
        services = data.get("account", {}).get("energy", {}).get("services", [])
        if not services:
            return None
        tariff = services[0].get("energyTariff", {})
        is_ev = tariff.get("isElectricVehicleTariff", False)
        return EnergyTariff(
            tariff_name="EV Tariff" if is_ev else "Standard Variable",
            tariff_code="EV" if is_ev else "SVT",
            unit_rate_pence=0.0,
            standing_charge_pence=0.0,
        )

    async def get_bills(self) -> list[Bill]:
        data = await self._client.graphql_request("GetBills", GET_BILLS)
        billing = data.get("customerBilling", {})
        bills_list = billing.get("accountBills", {}).get("billsList", [])
        results: list[Bill] = []
        for b in bills_list:
            invoice_date = b.get("invoiceDate", {})
            seconds = invoice_date.get("seconds", 0)
            bill_dt = datetime.fromtimestamp(seconds, tz=UTC).date()
            total = b.get("total", {})
            pdf_url = b.get("url")

            pdf_meta = None
            if pdf_url and isinstance(pdf_url, str):
                pdf_meta = BillPDFMetadata(pdf_url=pdf_url)

            results.append(
                Bill(
                    bill_id=b.get("invoiceId", ""),
                    account_id="",
                    bill_date=bill_dt,
                    period_start=bill_dt,
                    period_end=bill_dt,
                    total_amount_gbp=float(total.get("value", 0)),
                    status=BillStatus.PAID,
                    pdf=pdf_meta,
                )
            )
        return results

    async def get_pdf_url(self, month: int, year: int) -> str:
        data = await self._client.graphql_request(
            "GetPdfUrl", GET_PDF_URL, {"month": month, "year": year}
        )
        return str(data.get("customerBilling", {}).get("pdfUrl", ""))

    async def get_balance(self) -> dict[str, Any]:
        account_id = (await self._get_account_id()) or ""
        data = await self._client.graphql_request("Balance", GET_BALANCE, {"id": account_id})
        finance = data.get("finance", {}).get("account", {})
        due = finance.get("dueBalance", {}).get("value", 0)
        overdue = finance.get("overdueBalance", {}).get("value", 0)
        return {
            "due": float(due) if due else 0.0,
            "overdue": float(overdue) if overdue else 0.0,
        }

    async def get_live_services(self) -> dict[str, Any]:
        account_id = (await self._get_account_id()) or ""
        data = await self._client.graphql_request(
            "GetLiveServices", GET_LIVE_SERVICES, {"accountId": account_id}
        )
        result = data.get("getDashboardServices", {})
        if isinstance(result, dict):
            return result
        return {}

    async def _get_account_id(self) -> str | None:
        data = await self._client.graphql_request("GetAccount", GET_ACCOUNT)
        account = data.get("account", {})
        aid = account.get("id")
        return str(aid) if aid else None
