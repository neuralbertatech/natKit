"""MarkerEventV1 JSON ABI binding.

The two-call transcoder machinery now lives in :mod:`natvr.libnatkit_schema`
(shared with the EMG schema added in Phase 3b). This module re-exports the
MarkerEventV1 wrappers for existing callers.
"""

from __future__ import annotations

from natvr.libnatkit_schema import (
    marker_event_decode_json,
    marker_event_encode_json,
)

__all__ = ["marker_event_encode_json", "marker_event_decode_json"]
