"""Canonical JSON serialisation and hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def dumps(obj: Any) -> bytes:
    """UTF-8, sorted keys, no whitespace, no NaN/Infinity, trailing newline."""
    text = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return text.encode("utf-8") + b"\n"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def id_sort_key(event_id: str) -> bytes:
    """UTF-8 byte order, as required by the contract (not UTF-16 or locale order)."""
    return event_id.encode("utf-8")
