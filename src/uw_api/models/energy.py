from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class UsageReading(BaseModel):
    date: datetime
    value: float
    unit: str = "kWh"
    reading_type: str = "actual"


class EnergyUsage(BaseModel):
    service_id: str
    meter_number: str
    readings: list[UsageReading] = Field(default_factory=list)
    total_consumption_kwh: float = 0.0
    period_start: date | None = None
    period_end: date | None = None


class EnergyTariff(BaseModel):
    tariff_name: str
    tariff_code: str
    unit_rate_pence: float
    standing_charge_pence: float
    payment_method: str | None = None
    tariff_end_date: date | None = None
    exit_fee: float | None = None


class EnergyConsumption(BaseModel):
    service_id: str
    period: str
    electricity_kwh: float | None = None
    gas_kwh: float | None = None
    electricity_cost_gbp: float | None = None
    gas_cost_gbp: float | None = None
    total_cost_gbp: float | None = None
