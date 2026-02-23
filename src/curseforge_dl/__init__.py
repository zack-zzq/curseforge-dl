"""
curseforge-dl: CurseForge modpack downloader.

Download mods, resource packs, and shader packs from CurseForge.
"""

from curseforge_dl.models import (
    CurseManifest,
    CurseManifestFile,
    CurseManifestMinecraft,
    ModLoader,
    CurseAddon,
    AddonFile,
)
from curseforge_dl.api import CurseForgeAPI
from curseforge_dl.installer import ModpackInstaller
from curseforge_dl.url import build_cdn_url, get_download_url
from curseforge_dl.fingerprint import curseforge_fingerprint

__all__ = [
    "CurseManifest",
    "CurseManifestFile",
    "CurseManifestMinecraft",
    "ModLoader",
    "CurseAddon",
    "AddonFile",
    "CurseForgeAPI",
    "ModpackInstaller",
    "build_cdn_url",
    "get_download_url",
    "curseforge_fingerprint",
]

__version__ = "0.1.0"
