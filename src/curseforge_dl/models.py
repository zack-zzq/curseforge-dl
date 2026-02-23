"""
Pydantic data models for CurseForge manifest and API responses.

Mirrors the Java classes from HMCL:
  CurseManifest, CurseManifestFile, CurseAddon, CurseAddon.LatestFile, etc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Manifest models (parsed from modpack zip) ──────────────────────


class ModLoader(BaseModel):
    """A mod loader entry inside the manifest (e.g. ``forge-47.2.0``)."""

    id: str
    primary: bool = False


class CurseManifestMinecraft(BaseModel):
    """Minecraft version and mod loaders section of the manifest."""

    version: str = ""
    mod_loaders: list[ModLoader] = Field(default_factory=list, alias="modLoaders")

    model_config = {"populate_by_name": True}


class CurseManifestFile(BaseModel):
    """
    A single file entry in the modpack manifest.

    The manifest normally only contains ``projectID`` and ``fileID``.
    ``fileName`` and ``url`` are resolved later via the API.
    """

    project_id: int = Field(alias="projectID")
    file_id: int = Field(alias="fileID")
    file_name: Optional[str] = Field(default=None, alias="fileName")
    url: Optional[str] = None
    required: bool = True

    model_config = {"populate_by_name": True}


class CurseManifest(BaseModel):
    """Top-level CurseForge modpack manifest (``manifest.json``)."""

    manifest_type: str = Field(default="minecraftModpack", alias="manifestType")
    manifest_version: int = Field(default=1, alias="manifestVersion")
    name: str = ""
    version: str = ""
    author: str = ""
    overrides: str = "overrides"
    minecraft: CurseManifestMinecraft = Field(default_factory=CurseManifestMinecraft)
    files: list[CurseManifestFile] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ── API response models ────────────────────────────────────────────


class AddonLinks(BaseModel):
    website_url: Optional[str] = Field(default=None, alias="websiteUrl")
    wiki_url: Optional[str] = Field(default=None, alias="wikiUrl")
    issues_url: Optional[str] = Field(default=None, alias="issuesUrl")
    source_url: Optional[str] = Field(default=None, alias="sourceUrl")

    model_config = {"populate_by_name": True}


class AddonAuthor(BaseModel):
    id: int = 0
    name: str = ""
    url: str = ""


class AddonLogo(BaseModel):
    id: int = 0
    mod_id: int = Field(default=0, alias="modId")
    title: str = ""
    description: str = ""
    thumbnail_url: str = Field(default="", alias="thumbnailUrl")
    url: str = ""

    model_config = {"populate_by_name": True}


class AddonCategory(BaseModel):
    id: int = 0
    game_id: int = Field(default=0, alias="gameId")
    name: str = ""
    slug: str = ""
    url: str = ""
    icon_url: str = Field(default="", alias="iconUrl")
    date_modified: Optional[datetime] = Field(default=None, alias="dateModified")
    is_class: bool = Field(default=False, alias="isClass")
    class_id: int = Field(default=0, alias="classId")
    parent_category_id: int = Field(default=0, alias="parentCategoryId")

    model_config = {"populate_by_name": True}


class AddonFileHash(BaseModel):
    """File hash as returned by the API."""

    value: str = ""
    algo: int = 0  # 1=sha1, 2=md5


class AddonFileDependency(BaseModel):
    """Dependency reference within an addon file."""

    mod_id: int = Field(default=0, alias="modId")
    relation_type: int = Field(default=1, alias="relationType")

    model_config = {"populate_by_name": True}


class AddonFile(BaseModel):
    """
    A specific file/version of a CurseForge addon.

    Mirrors ``CurseAddon.LatestFile`` in HMCL.
    """

    id: int = 0
    game_id: int = Field(default=0, alias="gameId")
    mod_id: int = Field(default=0, alias="modId")
    is_available: bool = Field(default=True, alias="isAvailable")
    display_name: str = Field(default="", alias="displayName")
    file_name: str = Field(default="", alias="fileName")
    release_type: int = Field(default=1, alias="releaseType")
    file_status: int = Field(default=0, alias="fileStatus")
    hashes: list[AddonFileHash] = Field(default_factory=list)
    file_date: Optional[datetime] = Field(default=None, alias="fileDate")
    file_length: int = Field(default=0, alias="fileLength")
    download_count: int = Field(default=0, alias="downloadCount")
    download_url: Optional[str] = Field(default=None, alias="downloadUrl")
    game_versions: list[str] = Field(default_factory=list, alias="gameVersions")
    dependencies: list[AddonFileDependency] = Field(default_factory=list)
    alternate_file_id: int = Field(default=0, alias="alternateFileId")
    is_server_pack: bool = Field(default=False, alias="isServerPack")
    file_fingerprint: int = Field(default=0, alias="fileFingerprint")

    model_config = {"populate_by_name": True}


class AddonFileIndex(BaseModel):
    game_version: str = Field(default="", alias="gameVersion")
    file_id: int = Field(default=0, alias="fileId")
    filename: str = ""
    release_type: int = Field(default=1, alias="releaseType")
    game_version_type_id: int = Field(default=0, alias="gameVersionTypeId")
    mod_loader: int = Field(default=0, alias="modLoader")

    model_config = {"populate_by_name": True}


class CurseAddon(BaseModel):
    """
    Full CurseForge addon/project metadata.

    Mirrors ``CurseAddon`` in HMCL.
    """

    id: int = 0
    game_id: int = Field(default=0, alias="gameId")
    name: str = ""
    slug: str = ""
    links: AddonLinks = Field(default_factory=AddonLinks)
    summary: str = ""
    status: int = 0
    download_count: int = Field(default=0, alias="downloadCount")
    is_featured: bool = Field(default=False, alias="isFeatured")
    primary_category_id: int = Field(default=0, alias="primaryCategoryId")
    categories: list[AddonCategory] = Field(default_factory=list)
    class_id: int = Field(default=0, alias="classId")
    authors: list[AddonAuthor] = Field(default_factory=list)
    logo: Optional[AddonLogo] = None
    main_file_id: int = Field(default=0, alias="mainFileId")
    latest_files: list[AddonFile] = Field(default_factory=list, alias="latestFiles")
    latest_file_indices: list[AddonFileIndex] = Field(
        default_factory=list, alias="latestFilesIndex"
    )
    date_created: Optional[datetime] = Field(default=None, alias="dateCreated")
    date_modified: Optional[datetime] = Field(default=None, alias="dateModified")
    date_released: Optional[datetime] = Field(default=None, alias="dateReleased")
    allow_mod_distribution: Optional[bool] = Field(
        default=None, alias="allowModDistribution"
    )
    game_popularity_rank: int = Field(default=0, alias="gamePopularityRank")
    is_available: bool = Field(default=True, alias="isAvailable")
    thumbs_up_count: int = Field(default=0, alias="thumbsUpCount")

    model_config = {"populate_by_name": True}


# ── Section / classId constants ────────────────────────────────────

SECTION_BUKKIT_PLUGIN = 5
SECTION_MOD = 6
SECTION_RESOURCE_PACK = 12
SECTION_WORLD = 17
SECTION_MODPACK = 4471
SECTION_CUSTOMIZATION = 4546
SECTION_SHADER_PACK = 6552
