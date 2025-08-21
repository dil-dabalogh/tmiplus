from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

from tmiplus.adapters.base import DataAdapter

if TYPE_CHECKING:  # for type-checkers only; avoid hard imports at runtime
    pass


def get_adapter() -> DataAdapter:
    """Return the active data adapter based on environment.

    Uses Airtable if both `TMI_AIRTABLE_API_KEY` and `TMI_AIRTABLE_BASE_ID` are set,
    otherwise falls back to the in-memory adapter (useful for tests/demos).
    """
    if os.getenv("TMI_AIRTABLE_API_KEY") and os.getenv("TMI_AIRTABLE_BASE_ID"):
        from tmiplus.adapters.airtable.adapter import AirtableAdapter

        return cast(DataAdapter, AirtableAdapter())

    from tmiplus.adapters.memory.adapter import MemoryAdapter

    return cast(DataAdapter, MemoryAdapter())
