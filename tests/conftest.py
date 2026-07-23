from __future__ import annotations

import pytest


@pytest.fixture
def dummy_config() -> dict:
    return {
        "base_url": "https://myaccount.uw.co.uk/api",
        "auth": {
            "login_url": "https://myaccount.uw.co.uk/api/login",
        },
        "endpoints": {},
    }
