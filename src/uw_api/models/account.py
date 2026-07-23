from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ServiceType(StrEnum):
    ENERGY = "energy"
    GAS = "gas"
    BROADBAND = "broadband"
    MOBILE = "mobile"
    INSURANCE = "insurance"
    BOILER_COVER = "boiler_cover"
    CASHBACK_CARD = "cashback_card"


class ServiceSummary(BaseModel):
    service_type: ServiceType
    service_id: str
    account_number: str
    status: str
    supply_address: str | None = None


class UWAccount(BaseModel):
    account_id: str
    account_number: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    services: list[ServiceSummary] = Field(default_factory=list)
    balance: float | None = None
    payment_method: str | None = None
