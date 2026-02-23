"""Tests for MurmurHash2 fingerprint computation."""

from curseforge_dl.fingerprint import (
    _murmur_hash2,
    _strip_whitespace,
    curseforge_fingerprint_bytes,
)


class TestMurmurHash2:
    def test_empty(self):
        result = _murmur_hash2(b"", seed=1)
        assert isinstance(result, int)

    def test_known_value(self):
        # "Hello" with seed 1
        result = _murmur_hash2(b"Hello", seed=1)
        assert isinstance(result, int)
        assert 0 <= result < 2**32

    def test_deterministic(self):
        data = b"test data for hashing"
        r1 = _murmur_hash2(data, seed=1)
        r2 = _murmur_hash2(data, seed=1)
        assert r1 == r2

    def test_different_seeds(self):
        data = b"test data"
        r1 = _murmur_hash2(data, seed=1)
        r2 = _murmur_hash2(data, seed=42)
        assert r1 != r2


class TestStripWhitespace:
    def test_strip(self):
        # 0x09=tab, 0x0a=newline, 0x0d=CR, 0x20=space
        data = b"a\tb\nc\rd e"
        result = _strip_whitespace(data)
        assert result == b"abcde"

    def test_no_whitespace(self):
        data = b"abcdef"
        assert _strip_whitespace(data) == data

    def test_all_whitespace(self):
        data = b"\t\n\r "
        assert _strip_whitespace(data) == b""


class TestCurseforgeFingerprint:
    def test_basic_fingerprint(self):
        data = b"public class MyMod { }"
        fp = curseforge_fingerprint_bytes(data)
        assert isinstance(fp, int)
        assert 0 <= fp < 2**32

    def test_whitespace_invariant(self):
        """Fingerprint should be the same regardless of whitespace."""
        data1 = b"public class MyMod{}"
        data2 = b"public class MyMod { }"
        data3 = b"public\tclass\nMyMod\r{}\r\n"
        fp1 = curseforge_fingerprint_bytes(data1)
        fp2 = curseforge_fingerprint_bytes(data2)
        fp3 = curseforge_fingerprint_bytes(data3)
        # After stripping whitespace, these should all be:
        # b"publicclassMyMod{}"
        assert fp1 == fp2 == fp3
