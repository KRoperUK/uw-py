from __future__ import annotations

import io
import re
from datetime import date

from uw_api.exceptions import UWPDFExtractError
from uw_api.models.bill import Bill, BillLineItem, BillStatus


def extract_bill_data(pdf_bytes: bytes) -> Bill:
    try:
        import pdfplumber
    except ImportError:
        raise UWPDFExtractError("pdfplumber is not installed") from None

    try:
        pdf_file = io.BytesIO(pdf_bytes)
        with pdfplumber.open(pdf_file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise UWPDFExtractError(f"Failed to open PDF: {exc}") from exc

    if not text.strip():
        raise UWPDFExtractError("PDF contains no extractable text")

    bill_id = _find_first(
        text,
        [
            r"Bill\s*(?:Number|ID|Ref)[:\s]*([\w\d-]+)",
            r"Invoice\s*(?:Number|ID|Ref)[:\s]*([\w\d-]+)",
        ],
    )
    account_id = _find_first(
        text,
        [
            r"Account\s*(?:Number|ID|No)[:\s]*(\d+)",
        ],
    )

    bill_date = _find_first(
        text,
        [
            r"Bill\s*[Dd]ate[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"Date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
    )
    period_start = _find_first(
        text,
        [
            r"[Pp]eriod[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|[-\u2013])\s*",
            r"[Ff]rom[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
    )
    period_end = _find_first(
        text,
        [
            r"(?:to|[-\u2013])\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
    )
    total_amount = _find_first(
        text,
        [
            r"(?:Total|Amount\s*Due)[:\s]*[£$]?([\d,.]+)",
            r"(?:Grand\s*Total)[:\s]*[£$]?([\d,.]+)",
        ],
    )
    due_date = _find_first(
        text,
        [
            r"[Dd]ue\s*[Dd]ate[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"[Pp]ayment\s*[Dd]ue[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ],
    )
    elec_usage = _find_first(
        text,
        [
            r"[Ee]lectricity[:\s]*(\d[\d,.]*)\s*kWh",
            r"[Ee]lec[:\s]*(\d[\d,.]*)\s*kWh",
        ],
    )
    gas_usage = _find_first(
        text,
        [
            r"[Gg]as[:\s]*(\d[\d,.]*)\s*kWh",
        ],
    )
    unit_rate = _find_first(
        text,
        [
            r"[Uu]nit\s*[Rr]ate[:\s]*(\d[\d,.]*)\s*p",
            r"[Pp]rice\s*per\s*kWh[:\s]*(\d[\d,.]*)\s*p",
        ],
    )
    standing_charge = _find_first(
        text,
        [
            r"[Ss]tanding\s*[Cc]harge[:\s]*[£$]?(\d[\d,.]*)\s*p?",
        ],
    )
    meter_start = _find_first(
        text,
        [
            r"[Pp]revious\s*[Rr]eading[:\s]*(\d[\d,.]*)",
            r"[Ss]tart\s*[Rr]eading[:\s]*(\d[\d,.]*)",
        ],
    )
    meter_end = _find_first(
        text,
        [
            r"[Cc]urrent\s*[Rr]eading[:\s]*(\d[\d,.]*)",
            r"[Ee]nd\s*[Rr]eading[:\s]*(\d[\d,.]*)",
        ],
    )

    line_items: list[BillLineItem] = []
    if unit_rate and elec_usage:
        line_items.append(
            BillLineItem(
                description="Electricity usage",
                amount_gbp=_to_float(elec_usage) * _to_float(unit_rate) / 100 if unit_rate else 0.0,
                quantity=_to_float(elec_usage),
                unit_rate_pence=_to_float(unit_rate) if unit_rate else None,
            )
        )
    if standing_charge:
        line_items.append(
            BillLineItem(
                description="Standing charge",
                amount_gbp=_to_float(standing_charge),
            )
        )

    return Bill(
        bill_id=bill_id or "unknown",
        account_id=account_id or "unknown",
        bill_date=_date_from_str(bill_date) if bill_date else None,  # type: ignore[arg-type]
        period_start=_date_from_str(period_start) if period_start else None,  # type: ignore[arg-type]
        period_end=_date_from_str(period_end) if period_end else None,  # type: ignore[arg-type]
        total_amount_gbp=_to_float(total_amount) if total_amount else 0.0,
        status=BillStatus.PENDING,
        due_date=_date_from_str(due_date) if due_date else None,
        line_items=line_items,
        pdf=None,
        electricity_usage_kwh=_to_float(elec_usage) if elec_usage else None,
        gas_usage_kwh=_to_float(gas_usage) if gas_usage else None,
        meter_reading_start=_to_float(meter_start) if meter_start else None,
        meter_reading_end=_to_float(meter_end) if meter_end else None,
    )


def _find_first(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _to_float(value: str) -> float:
    return float(value.replace(",", "").strip())


def _date_from_str(value: str) -> date | None:
    separators = ["/", "-"]
    for sep in separators:
        parts = value.split(sep)
        if len(parts) == 3:
            d, m, y = parts
            if len(y) == 2:
                y = f"20{y}"
            return date(int(y), int(m), int(d))
    return None
