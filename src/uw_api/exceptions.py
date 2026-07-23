from __future__ import annotations


class UWApiError(Exception):
    pass


class UWAuthError(UWApiError):
    pass


class UWSessionExpiredError(UWApiError):
    pass


class UWRateLimitError(UWApiError):
    pass


class UWDataParseError(UWApiError):
    pass


class UWPDFExtractError(UWApiError):
    pass
