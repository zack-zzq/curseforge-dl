"""Tests for manifest model parsing."""

import json
import zipfile
from pathlib import Path

from curseforge_dl.models import CurseManifest, CurseManifestFile


TEST_ZIP = Path(__file__).parent.parent / "All the Mods 10-5.5.zip"


class TestCurseManifestFile:
    def test_url_generation_with_url(self):
        f = CurseManifestFile(
            projectID=12345,
            fileID=6789012,
            fileName="test.jar",
            url="https://example.com/test.jar",
        )
        assert f.url == "https://example.com/test.jar"

    def test_fields(self):
        f = CurseManifestFile(projectID=699872, fileID=5433036, required=True)
        assert f.project_id == 699872
        assert f.file_id == 5433036
        assert f.required is True
        assert f.file_name is None
        assert f.url is None

    def test_serialize_by_alias(self):
        f = CurseManifestFile(projectID=699872, fileID=5433036, required=True)
        data = json.loads(f.model_dump_json(by_alias=True))
        assert data["projectID"] == 699872
        assert data["fileID"] == 5433036


class TestCurseManifestFromZip:
    """Integration tests that require the test zip file to be present."""

    def test_parse_real_manifest(self):
        if not TEST_ZIP.exists():
            return  # Skip if test data not available

        with zipfile.ZipFile(TEST_ZIP, "r") as zf:
            raw = json.loads(zf.read("manifest.json"))
            manifest = CurseManifest.model_validate(raw)

        assert manifest.name == "All the Mods 10"
        assert manifest.version == "5.5"
        assert manifest.author == "ATMTeam"
        assert manifest.manifest_type == "minecraftModpack"
        assert manifest.overrides == "overrides"

        # Minecraft info
        assert manifest.minecraft.version == "1.21.1"
        assert len(manifest.minecraft.mod_loaders) >= 1
        loader = manifest.minecraft.mod_loaders[0]
        assert loader.id.startswith("neoforge-")

        # Files
        assert len(manifest.files) == 480
        first = manifest.files[0]
        assert first.project_id == 699872
        assert first.file_id == 5433036
        assert first.required is True

    def test_roundtrip_serialization(self):
        if not TEST_ZIP.exists():
            return

        with zipfile.ZipFile(TEST_ZIP, "r") as zf:
            raw = json.loads(zf.read("manifest.json"))
            manifest = CurseManifest.model_validate(raw)

        # Serialize and re-parse
        serialized = json.loads(manifest.model_dump_json(by_alias=True))
        manifest2 = CurseManifest.model_validate(serialized)

        assert manifest2.name == manifest.name
        assert len(manifest2.files) == len(manifest.files)
        assert manifest2.minecraft.version == manifest.minecraft.version
