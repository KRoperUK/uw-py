from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class BillStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class BillLineItem(BaseModel):
    description: str
    amount_gbp: float
    quantity: float | None = None
    unit_rate_pence: float | None = None
    vat_gbp: float | None = None


class BillPDFMetadata(BaseModel):
    pdf_url: str | None = None
    filename: str | None = None
    generated_at: datetime | None = None


class Bill(BaseModel):
    bill_id: str
    account_id: str
    bill_date: date
    period_start: date
    period_end: date
    total_amount_gbp: float
    status: BillStatus
    due_date: date | None = None
    paid_date: date | None = None
    line_items: list[BillLineItem] = Field(default_factory=list)
    pdf: BillPDFMetadata | None = None
    electricity_usage_kwh: float | None = None
    gas_usage_kwh: float | None = None
    meter_reading_start: float | None = None
    meter_reading_end: float | None = None
