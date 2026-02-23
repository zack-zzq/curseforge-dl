"""
MurmurHash2 fingerprint computation for CurseForge.

CurseForge uses a **MurmurHash2** (32-bit, seed=1) to fingerprint mod files.
Before hashing, all whitespace bytes (``0x09``, ``0x0a``, ``0x0d``, ``0x20``)
are stripped from the file content.

This is used to match a local mod file against CurseForge's fingerprint
database via ``POST /v1/fingerprints/432``.
"""

from __future__ import annotations

import struct
from pathlib import Path

# Whitespace bytes to strip before hashing
_WHITESPACE = {0x09, 0x0A, 0x0D, 0x20}


def _murmur_hash2(data: bytes, seed: int = 1) -> int:
    """
    Compute MurmurHash2 (32-bit) matching CurseForge's implementation.

    This produces an **unsigned** 32-bit integer identical to
    ``MurmurHash2.hash32()`` in HMCL / CurseForge.
    """
    length = len(data)
    m = 0x5BD1E995
    r = 24
    h = seed ^ length
    mask = 0xFFFFFFFF

    i = 0
    while length >= 4:
        k = struct.unpack_from("<I", data, i)[0]
        k = (k * m) & mask
        k ^= (k >> r)
        k = (k * m) & mask

        h = (h * m) & mask
        h = (h ^ k) & mask

        i += 4
        length -= 4

    if length == 3:
        h ^= data[i + 2] << 16
    if length >= 2:
        h ^= data[i + 1] << 8
    if length >= 1:
        h ^= data[i]
        h = (h * m) & mask

    h ^= (h >> 13)
    h = (h * m) & mask
    h ^= (h >> 15)

    return h


def _strip_whitespace(data: bytes) -> bytes:
    """Remove CurseForge-specific whitespace bytes from file content."""
    return bytes(b for b in data if b not in _WHITESPACE)


def curseforge_fingerprint(file_path: str | Path) -> int:
    """
    Compute the CurseForge fingerprint for a local file.

    Steps:
      1. Read the entire file.
      2. Strip whitespace bytes (tab, newline, carriage-return, space).
      3. Compute MurmurHash2 with seed=1.

    Returns the unsigned 32-bit fingerprint as a Python int.
    """
    raw = Path(file_path).read_bytes()
    stripped = _strip_whitespace(raw)
    return _murmur_hash2(stripped, seed=1)


def curseforge_fingerprint_bytes(data: bytes) -> int:
    """
    Compute the CurseForge fingerprint for raw bytes.

    Same as :func:`curseforge_fingerprint` but operates on in-memory data.
    """
    stripped = _strip_whitespace(data)
    return _murmur_hash2(stripped, seed=1)
