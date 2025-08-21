from __future__ import annotations
import os
from tmiplus.adapters.memory.adapter import MemoryAdapter
from tmiplus.adapters.airtable.adapter import AirtableAdapter

def get_adapter():
    """Return the active data adapter based on environment.

    Uses Airtable if both `TMI_AIRTABLE_API_KEY` and `TMI_AIRTABLE_BASE_ID` are set,
    otherwise falls back to the in-memory adapter (useful for tests/demos).
    """
    if os.getenv("TMI_AIRTABLE_API_KEY") and os.getenv("TMI_AIRTABLE_BASE_ID"):
        return AirtableAdapter()
    return MemoryAdapter()


