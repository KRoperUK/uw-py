from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class MeterType(StrEnum):
    ELECTRICITY = "electricity"
    GAS = "gas"


class Meter(BaseModel):
    meter_id: str
    service_id: str
    meter_type: MeterType
    meter_number: str
    mpan: str | None = None
    mprn: str | None = None
    is_smart: bool = False
    last_reading_date: datetime | None = None


class MeterReading(BaseModel):
    reading_id: str | None = None
    meter_id: str
    reading_date: datetime
    value: float
    unit: str = "kWh"
    reading_type: str = "actual"
    source: str = "customer"
