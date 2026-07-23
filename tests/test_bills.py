from __future__ import annotations

import pytest

from uw_api.exceptions import UWPDFExtractError
from uw_api.pdf.extractor import extract_bill_data


class TestPDFExtractor:
    def test_invalid_pdf_raises_error(self) -> None:
        with pytest.raises(UWPDFExtractError, match="Failed to open PDF"):
            extract_bill_data(b"not a valid pdf")
