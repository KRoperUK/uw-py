from __future__ import annotations

from datetime import date
from typing import Any

from uw_api.models.account import ServiceType, UWAccount
from uw_api.models.bill import Bill, BillStatus
from uw_api.models.energy import (
    EnergyConsumption,
    EnergyTariff,
    EnergyUsage,
    UsageReading,
)
from uw_api.models.meter import Meter, MeterReading, MeterType


class TestUWAccount:
    def test_minimal_account(self) -> None:
        data: dict[str, Any] = {
            "account_id": "ACC123",
            "account_number": "12345678",
            "email": "test@example.com",
        }
        account = UWAccount.model_validate(data)
        assert account.account_id == "ACC123"
        assert account.services == []

    def test_account_with_services(self) -> None:
        data: dict[str, Any] = {
            "account_id": "ACC123",
            "account_number": "12345678",
            "email": "test@example.com",
            "services": [
                {
                    "service_type": "energy",
                    "service_id": "SVC1",
                    "account_number": "E12345",
                    "status": "active",
                    "supply_address": "1 Test Street",
                }
            ],
        }
        account = UWAccount.model_validate(data)
        assert len(account.services) == 1
        assert account.services[0].service_type == ServiceType.ENERGY
        assert account.services[0].supply_address == "1 Test Street"

    def test_balance_and_payment(self) -> None:
        data: dict[str, Any] = {
            "account_id": "ACC123",
            "account_number": "12345678",
            "email": "test@example.com",
            "balance": -50.25,
            "payment_method": "direct_debit",
        }
        account = UWAccount.model_validate(data)
        assert account.balance == -50.25
        assert account.payment_method == "direct_debit"


class TestEnergyModels:
    def test_usage_reading(self) -> None:
        data: dict[str, Any] = {
            "date": "2025-01-15T00:00:00Z",
            "value": 12.5,
            "unit": "kWh",
            "reading_type": "actual",
        }
        reading = UsageReading.model_validate(data)
        assert reading.value == 12.5
        assert reading.unit == "kWh"

    def test_energy_usage(self) -> None:
        data: dict[str, Any] = {
            "service_id": "SVC1",
            "meter_number": "M12345",
            "readings": [
                {"date": "2025-01-01T00:00:00Z", "value": 100.0},
                {"date": "2025-01-02T00:00:00Z", "value": 105.0},
            ],
            "total_consumption_kwh": 5.0,
        }
        usage = EnergyUsage.model_validate(data)
        assert len(usage.readings) == 2
        assert usage.total_consumption_kwh == 5.0

    def test_energy_tariff(self) -> None:
        data: dict[str, Any] = {
            "tariff_name": "UW Fixed Saver",
            "tariff_code": "FIX-2025",
            "unit_rate_pence": 24.5,
            "standing_charge_pence": 50.0,
            "tariff_end_date": "2026-01-01",
        }
        tariff = EnergyTariff.model_validate(data)
        assert tariff.unit_rate_pence == 24.5
        assert tariff.tariff_end_date == date(2026, 1, 1)

    def test_energy_consumption(self) -> None:
        data: dict[str, Any] = {
            "service_id": "SVC1",
            "period": "2025-01",
            "electricity_kwh": 250.0,
            "gas_kwh": 150.0,
            "total_cost_gbp": 85.50,
        }
        consumption = EnergyConsumption.model_validate(data)
        assert consumption.electricity_kwh == 250.0
        assert consumption.gas_kwh == 150.0


class TestBillModels:
    def test_bill(self) -> None:
        data: dict[str, Any] = {
            "bill_id": "BILL-001",
            "account_id": "ACC123",
            "bill_date": "2025-01-15",
            "period_start": "2025-01-01",
            "period_end": "2025-01-31",
            "total_amount_gbp": 120.50,
            "status": "paid",
        }
        bill = Bill.model_validate(data)
        assert bill.total_amount_gbp == 120.50
        assert bill.status == BillStatus.PAID
        assert bill.bill_date == date(2025, 1, 15)

    def test_bill_with_line_items(self) -> None:
        data: dict[str, Any] = {
            "bill_id": "BILL-001",
            "account_id": "ACC123",
            "bill_date": "2025-01-15",
            "period_start": "2025-01-01",
            "period_end": "2025-01-31",
            "total_amount_gbp": 120.50,
            "status": "paid",
            "line_items": [
                {
                    "description": "Electricity",
                    "amount_gbp": 80.0,
                    "quantity": 320.0,
                    "unit_rate_pence": 25.0,
                }
            ],
        }
        bill = Bill.model_validate(data)
        assert len(bill.line_items) == 1
        assert bill.line_items[0].amount_gbp == 80.0

    def test_bill_pdf_metadata(self) -> None:
        data: dict[str, Any] = {
            "bill_id": "BILL-001",
            "account_id": "ACC123",
            "bill_date": "2025-01-15",
            "period_start": "2025-01-01",
            "period_end": "2025-01-31",
            "total_amount_gbp": 120.50,
            "status": "paid",
            "pdf": {
                "pdf_url": "https://example.com/bill.pdf",
                "filename": "bill-001.pdf",
            },
        }
        bill = Bill.model_validate(data)
        assert bill.pdf is not None
        assert bill.pdf.pdf_url == "https://example.com/bill.pdf"


class TestMeterModels:
    def test_meter(self) -> None:
        data: dict[str, Any] = {
            "meter_id": "MTR1",
            "service_id": "SVC1",
            "meter_type": "electricity",
            "meter_number": "E123456789",
            "mpan": "1234567890123",
            "is_smart": True,
        }
        meter = Meter.model_validate(data)
        assert meter.meter_type == MeterType.ELECTRICITY
        assert meter.is_smart is True
        assert meter.mpan == "1234567890123"

    def test_meter_reading(self) -> None:
        data: dict[str, Any] = {
            "meter_id": "MTR1",
            "reading_date": "2025-01-15T12:00:00Z",
            "value": 12345.6,
            "unit": "kWh",
            "reading_type": "actual",
            "source": "smart_meter",
        }
        reading = MeterReading.model_validate(data)
        assert reading.value == 12345.6
        assert reading.source == "smart_meter"
