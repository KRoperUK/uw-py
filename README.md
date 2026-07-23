# uw-api

Async Python client for the Utility Warehouse customer portal API.

Endpoints are hardcoded (discovered from `myaccount.uw.co.uk/`) and require no
configuration — just provide credentials.

## Installation

```bash
pip install uw-api
```

## Usage

```python
import asyncio
from uw_api import UWClient

async def main():
    async with UWClient(email="user@example.com", password="secret") as client:
        await client.login()

        account = await client.gql.get_account()
        print(f"Account: {account.account_number}")

        bills = await client.gql.get_bills()
        for bill in bills:
            print(f"Bill {bill.bill_id}: £{bill.total_amount_gbp}")

        consumption = await client.gql.get_consumption()
        print(f"Electricity: {consumption.electricity_kwh} kWh")
        print(f"Gas: {consumption.gas_kwh} kWh")

        meters = await client.gql.get_meters()
        for meter in meters:
            print(f"{meter.meter_type}: {meter.meter_number} (smart={meter.is_smart})")

        tariff = await client.gql.get_tariff()
        if tariff:
            print(f"Tariff: {tariff.tariff_name}")

asyncio.run(main())
```

## API Reference

### Auth

```python
client = UWClient(email="...", password="...")
await client.login()
```

Authenticates via OAuth2 PKCE at `account.uw.co.uk/v2/login`. Session cookies are
managed automatically. The library re-authenticates on 401 responses.

### Account

```python
account = await client.gql.get_account()
```

Returns `UWAccount` with `account_id` and `account_number`.

### Energy

```python
consumption = await client.gql.get_consumption()
services   = await client.gql.get_energy_services()
usage      = await client.gql.get_energy_usage()
```

- `get_consumption()` → `EnergyConsumption` (latest electricity/gas kWh)
- `get_energy_services()` → raw list of energy service dicts
- `get_energy_usage()` → list of `EnergyUsage` with per-meter readings

### Meters

```python
meters   = await client.gql.get_meters()
readings = await client.gql.get_meter_readings()
```

- `get_meters()` → list of `Meter` (type, serial, smart status, last reading date)
- `get_meter_readings()` → list of `MeterReading` (value, type, date, source)

### Bills

```python
bills   = await client.gql.get_bills()
pdf_url = await client.gql.get_pdf_url(month=1, year=2026)
```

- `get_bills()` → list of `Bill` (ID, date, amount, status, PDF URL)
- `get_pdf_url(month, year)` → str URL for the bill PDF

### Financial

```python
balance  = await client.gql.get_balance()
services = await client.gql.get_live_services()
tariff   = await client.gql.get_tariff()
```

- `get_balance()` → `{"due": float, "overdue": float}`
- `get_live_services()` → dict of service statuses
- `get_tariff()` → `EnergyTariff` (name, code, rates)

## Hardcoded Endpoints

| Purpose | URL |
|---------|-----|
| Login page | `https://account.uw.co.uk/v2/login` |
| GraphQL API | `https://myaccount.uw.co.uk/server/graphql` |

11 GraphQL operations are embedded in `uw_api/graphql/queries.py`.

## Discovery Script (optional)

A HAR-based discovery script is included for verifying or re-discovering endpoints:

```bash
python scripts/discover_api.py parse-har capture.har
```

This is **not required** for normal use — the library ships with hardcoded
endpoints discovered from `myaccount.uw.co.uk/` in July 2026.

## Architecture

```
UWClient → UWAuth (OAuth2 PKCE)
         → UWGraphQL → /server/graphql (POST)
                      → Pydantic v2 models
```

- **Auth**: CSRF token extraction from login page HTML, form-encoded POST with
  Castle.io device token
- **GraphQL**: All data via `POST /server/graphql` with operation-oriented queries
- **Retry**: 3 attempts with exponential backoff on 429/5xx, re-auth on 401
- **Models**: `UWAccount`, `EnergyUsage`, `EnergyConsumption`, `EnergyTariff`,
  `Meter`, `MeterReading`, `Bill`, `BillPDFMetadata`
