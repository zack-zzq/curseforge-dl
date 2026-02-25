"""
Async CurseForge API client.

Wraps the CurseForge v1 REST API with an :class:`httpx.AsyncClient`, adding
automatic API key header injection and concurrency limiting (semaphore).

Reference: https://docs.curseforge.com/
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

# Load .env so CURSEFORGE_API_KEY can be set via .env file
load_dotenv()

from curseforge_dl.models import (
    AddonFile,
    CurseAddon,
    AddonCategory,
)

DEFAULT_API_BASE = "https://api.curseforge.com"
MINECRAFT_GAME_ID = 432
DEFAULT_CONCURRENCY = 16


class CurseForgeAPI:
    """
    Async client for the CurseForge v1 API.

    Usage::

        async with CurseForgeAPI(api_key="...") as api:
            mod = await api.get_mod(238222)
            print(mod.name)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = DEFAULT_API_BASE,
        concurrency: int = DEFAULT_CONCURRENCY,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.environ.get("CURSEFORGE_API_KEY", "")
        self.api_base = api_base.rstrip("/")
        self._semaphore = asyncio.Semaphore(concurrency)
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    @property
    def is_available(self) -> bool:
        """Whether an API key is configured."""
        return bool(self.api_key)

    async def __aenter__(self) -> CurseForgeAPI:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ── Low-level helpers ──────────────────────────────────────────

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        async with self._semaphore:
            resp = await self._client.get(
                f"{self.api_base}{path}", params=params
            )
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, json_body: dict) -> dict:
        async with self._semaphore:
            resp = await self._client.post(
                f"{self.api_base}{path}", json=json_body
            )
            resp.raise_for_status()
            return resp.json()

    # ── Mod search & lookup ────────────────────────────────────────

    async def search_mods(
        self,
        search_filter: str = "",
        game_version: str = "",
        class_id: int = 6,
        category_id: int = 0,
        sort_field: int = 2,
        sort_order: str = "desc",
        page_size: int = 20,
        index: int = 0,
        slug: str = "",
    ) -> list[CurseAddon]:
        """
        Search for mods/addons on CurseForge.

        ``class_id`` values:
          - 6 = Mods
          - 12 = Resource Packs
          - 17 = Worlds
          - 4471 = Modpacks
          - 6552 = Shader Packs

        ``sort_field`` values (ModsSearchSortField):
          - 1 = DateCreated
          - 2 = Popularity
          - 3 = LastUpdated
          - 4 = Name
          - 5 = Author
          - 6 = TotalDownloads
        """
        params: dict[str, str | int] = {
            "gameId": MINECRAFT_GAME_ID,
            "classId": class_id,
            "sortField": sort_field,
            "sortOrder": sort_order,
            "pageSize": page_size,
            "index": index,
        }
        if search_filter:
            params["searchFilter"] = search_filter
        if game_version:
            params["gameVersion"] = game_version
        if category_id:
            params["categoryId"] = category_id
        if slug:
            params["slug"] = slug

        data = await self._get("/v1/mods/search", params=params)
        return [CurseAddon.model_validate(item) for item in data.get("data", [])]

    async def get_mod(self, mod_id: int) -> CurseAddon:
        """Get a single mod/addon by its ID."""
        data = await self._get(f"/v1/mods/{mod_id}")
        return CurseAddon.model_validate(data["data"])

    async def get_mod_by_slug(
        self, slug: str, class_id: int = 6
    ) -> Optional[CurseAddon]:
        """
        Find a mod/addon by its slug.

        Uses the search API with the ``slug`` parameter and returns the first
        exact match, or ``None`` if no match is found.

        Args:
            slug: The project slug (e.g. ``"all-the-mods-10"``).
            class_id: Class ID to filter by (default 6=Mods, 4471=Modpacks).
        """
        results = await self.search_mods(slug=slug, class_id=class_id, page_size=5)
        for addon in results:
            if addon.slug == slug:
                return addon
        return None

    async def get_mod_file(self, mod_id: int, file_id: int) -> AddonFile:
        """Get a specific file for a mod."""
        data = await self._get(f"/v1/mods/{mod_id}/files/{file_id}")
        return AddonFile.model_validate(data["data"])

    async def get_mod_files(
        self, mod_id: int, page_size: int = 10000
    ) -> list[AddonFile]:
        """Get all files for a mod."""
        data = await self._get(
            f"/v1/mods/{mod_id}/files", params={"pageSize": page_size}
        )
        return [AddonFile.model_validate(item) for item in data.get("data", [])]

    async def get_mod_file_download_url(self, mod_id: int, file_id: int) -> str:
        """
        Get the download URL for a specific file via the API.

        Uses ``GET /v1/mods/{modId}/files/{fileId}/download-url``.
        Falls back to CDN URL construction if the API returns no URL.
        """
        data = await self._get(f"/v1/mods/{mod_id}/files/{file_id}/download-url")
        url = data.get("data", "")
        if url:
            return url
        # Fallback: get file info and build CDN URL
        addon_file = await self.get_mod_file(mod_id, file_id)
        from curseforge_dl.url import build_cdn_url
        return build_cdn_url(addon_file.id, addon_file.file_name)

    async def get_categories(self) -> list[AddonCategory]:
        """Get all categories for Minecraft."""
        data = await self._get(
            "/v1/categories", params={"gameId": MINECRAFT_GAME_ID}
        )
        return [AddonCategory.model_validate(item) for item in data.get("data", [])]

    # ── Fingerprint matching ───────────────────────────────────────

    async def get_fingerprint_matches(
        self, fingerprints: list[int]
    ) -> list[dict]:
        """
        Match file fingerprints against CurseForge's database.

        Returns the raw ``exactMatches`` list from the API response.
        """
        data = await self._post(
            f"/v1/fingerprints/{MINECRAFT_GAME_ID}",
            {"fingerprints": fingerprints},
        )
        return data.get("data", {}).get("exactMatches", [])
