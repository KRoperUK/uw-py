# uw-api

Async Python client for the Utility Warehouse customer portal API.

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
        account = await client.get_account()
        print(account)
        bills = await client.list_bills()
        print(bills)

asyncio.run(main())
```

## Discovery

Before using the library, API endpoints must be discovered. Run the discovery helper:

```bash
python scripts/discover_api.py
```

Follow the instructions to capture network traffic from `myaccount.uw.co.uk/`.
