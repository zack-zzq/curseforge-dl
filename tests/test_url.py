"""Tests for CDN URL construction."""

from curseforge_dl.url import build_cdn_url, get_download_url
from curseforge_dl.models import AddonFile


class TestBuildCdnUrl:
    def test_basic(self):
        url = build_cdn_url(5433036, "somefile.jar")
        assert url == "https://edge.forgecdn.net/files/5433/36/somefile.jar"

    def test_round_file_id(self):
        url = build_cdn_url(4000000, "mod.jar")
        assert url == "https://edge.forgecdn.net/files/4000/0/mod.jar"

    def test_small_file_id(self):
        url = build_cdn_url(1234, "test.jar")
        assert url == "https://edge.forgecdn.net/files/1/234/test.jar"

    def test_large_file_id(self):
        url = build_cdn_url(7417441, "jei-1.21.1-19.19.2.jar")
        assert url == "https://edge.forgecdn.net/files/7417/441/jei-1.21.1-19.19.2.jar"

    def test_file_name_with_spaces(self):
        url = build_cdn_url(1234567, "My Mod File.jar")
        assert url == "https://edge.forgecdn.net/files/1234/567/My Mod File.jar"


class TestGetDownloadUrl:
    def test_with_download_url(self):
        f = AddonFile(
            id=123,
            fileName="test.jar",
            downloadUrl="https://example.com/test.jar",
        )
        assert get_download_url(f) == "https://example.com/test.jar"

    def test_without_download_url(self):
        f = AddonFile(
            id=5433036,
            fileName="somefile.jar",
            downloadUrl=None,
        )
        assert get_download_url(f) == "https://edge.forgecdn.net/files/5433/36/somefile.jar"

    def test_empty_download_url(self):
        f = AddonFile(
            id=5433036,
            fileName="somefile.jar",
            downloadUrl="",
        )
        assert get_download_url(f) == "https://edge.forgecdn.net/files/5433/36/somefile.jar"
