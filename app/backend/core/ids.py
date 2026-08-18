"""Sortable, prefixed IDs (Crockford-base32 ULIDs) for every entity in the system.

Chosen over autoincrement so an ID is stable before the owning row is
committed (it has to name an artifact directory first), and over UUID4 so
IDs sort by creation time, which makes run/entity directories on disk list
in chronological order without touching the DB.
"""

import os
import time

_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIMESTAMP_CHARS = 10
_RANDOMNESS_CHARS = 16
_RANDOMNESS_BYTES = 10


def _encode_base32(value: int, length: int) -> str:
    chars = [""] * length
    for i in range(length - 1, -1, -1):
        chars[i] = _CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


def generate_ulid(timestamp_ms: int | None = None) -> str:
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    time_part = _encode_base32(timestamp_ms, _TIMESTAMP_CHARS)
    random_int = int.from_bytes(os.urandom(_RANDOMNESS_BYTES), "big")
    random_part = _encode_base32(random_int, _RANDOMNESS_CHARS)
    return time_part + random_part


def new_id(prefix: str) -> str:
    return f"{prefix}-{generate_ulid()}"
