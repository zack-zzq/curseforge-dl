"""
CDN URL construction for CurseForge file downloads.

When the CurseForge API returns ``downloadUrl = null`` (because the mod author
has disabled third-party distribution), we can still construct a working
download URL from the **fileID** and **fileName** using CurseForge's CDN
pattern on ``edge.forgecdn.net``.

URL pattern::

    https://edge.forgecdn.net/files/{fileID // 1000}/{fileID % 1000}/{fileName}

Example::

    fileID = 5433036, fileName = "somefile.jar"
    → https://edge.forgecdn.net/files/5433/36/somefile.jar
"""

from __future__ import annotations

from curseforge_dl.models import AddonFile


def build_cdn_url(file_id: int, file_name: str) -> str:
    """
    Construct a CurseForge CDN download URL from a file ID and file name.

    This mirrors the fallback logic in HMCL's ``CurseAddon.LatestFile.getDownloadUrl()``
    and ``CurseManifestFile.getUrl()``.
    """
    return f"https://edge.forgecdn.net/files/{file_id // 1000}/{file_id % 1000}/{file_name}"


def get_download_url(addon_file: AddonFile) -> str:
    """
    Return the download URL for an :class:`AddonFile`.

    Uses ``downloadUrl`` from the API response when available; otherwise falls
    back to the constructed CDN URL.
    """
    if addon_file.download_url:
        return addon_file.download_url
    return build_cdn_url(addon_file.id, addon_file.file_name)
