"""
CurseForge modpack installer.

Handles the complete flow of installing a CurseForge modpack:
  1. Parse ``manifest.json`` from the modpack zip
  2. Extract override files to the output directory
  3. Resolve file names and download URLs via the CurseForge API
  4. Download all mod/resource-pack/shader-pack files in parallel
  5. Write the resolved manifest to the output directory

Mirrors the logic of ``CurseInstallTask`` + ``CurseCompletionTask`` in HMCL.
"""

from __future__ import annotations

import asyncio
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

import httpx
from tqdm import tqdm

from curseforge_dl.api import CurseForgeAPI
from curseforge_dl.models import (
    AddonFile,
    CurseAddon,
    CurseManifest,
    CurseManifestFile,
    SECTION_MOD,
    SECTION_MODPACK,
    SECTION_RESOURCE_PACK,
    SECTION_SHADER_PACK,
)
from curseforge_dl.url import build_cdn_url, get_download_url

logger = logging.getLogger(__name__)


class ModpackInstaller:
    """
    Install a CurseForge modpack from a zip file.

    Usage::

        async with CurseForgeAPI(api_key="...") as api:
            installer = ModpackInstaller(api)
            await installer.install("modpack.zip", "./minecraft")
    """

    def __init__(
        self,
        api: CurseForgeAPI,
        concurrency: int = 16,
        download_timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self.api = api
        self._concurrency = concurrency
        self._download_timeout = download_timeout
        self._max_retries = max_retries

    # ── Public entry point ─────────────────────────────────────────

    async def install(
        self,
        zip_path: str | Path,
        output_dir: str | Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> CurseManifest:
        """
        Install a CurseForge modpack.

        Args:
            zip_path: Path to the modpack ``.zip`` file.
            output_dir: Directory to install into (game run directory).
            progress_callback: Optional ``(current, total, message)`` callback.

        Returns:
            The resolved :class:`CurseManifest` with file names and URLs filled in.
        """
        zip_path = Path(zip_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Parse manifest
        manifest = self._parse_manifest(zip_path)
        logger.info(
            "Modpack: %s v%s by %s (%d files)",
            manifest.name,
            manifest.version,
            manifest.author,
            len(manifest.files),
        )

        # 2. Extract overrides
        self._extract_overrides(zip_path, output_dir, manifest.overrides)

        # 3. Resolve file info (fileName + downloadUrl) via API
        resolved_files = await self._resolve_files(manifest.files, progress_callback)

        # 4. Download all files
        await self._download_files(resolved_files, output_dir, progress_callback)

        # 5. Save resolved manifest
        resolved_manifest = CurseManifest(
            manifestType=manifest.manifest_type,
            manifestVersion=manifest.manifest_version,
            name=manifest.name,
            version=manifest.version,
            author=manifest.author,
            overrides=manifest.overrides,
            minecraft=manifest.minecraft,
            files=resolved_files,
        )
        manifest_out = output_dir / "manifest.json"
        manifest_out.write_text(
            resolved_manifest.model_dump_json(indent=2, by_alias=True),
            encoding="utf-8",
        )
        logger.info("Resolved manifest saved to %s", manifest_out)

        return resolved_manifest

    # ── Download modpack by slug ──────────────────────────────────

    async def download_modpack_by_slug(
        self,
        slug: str,
        output_dir: str | Path = ".",
        game_version: str = "",
    ) -> tuple[Path, CurseAddon, AddonFile]:
        """
        Look up a modpack by its slug and download the latest version zip.

        Args:
            slug: The modpack slug (e.g. ``"all-the-mods-10"``).
            output_dir: Directory to save the zip file into.
            game_version: Optional Minecraft version filter for file selection.

        Returns:
            A tuple of ``(zip_path, addon, file)`` where ``zip_path`` is the
            local path to the downloaded zip, ``addon`` is the modpack metadata,
            and ``file`` is the downloaded file metadata.

        Raises:
            ValueError: If the modpack or a suitable file cannot be found.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Find the modpack by slug
        addon = await self.api.get_mod_by_slug(slug, class_id=SECTION_MODPACK)
        if addon is None:
            raise ValueError(f"Modpack not found: '{slug}'")

        logger.info("Found modpack: %s (ID=%d)", addon.name, addon.id)

        # 2. Select the best (latest) file
        latest_file = self._select_latest_file(addon, game_version)
        if latest_file is None:
            raise ValueError(
                f"No downloadable file found for modpack '{addon.name}'"
                + (f" (game version: {game_version})" if game_version else "")
            )

        logger.info(
            "Latest file: %s (ID=%d, %s)",
            latest_file.display_name or latest_file.file_name,
            latest_file.id,
            f"{latest_file.file_length / 1024 / 1024:.1f} MB"
            if latest_file.file_length
            else "size unknown",
        )

        # 3. Resolve download URL
        download_url = get_download_url(latest_file)
        if not download_url:
            # Fallback via API endpoint
            download_url = await self.api.get_mod_file_download_url(
                addon.id, latest_file.id
            )

        # 4. Download the file
        target = output_dir / latest_file.file_name
        if target.exists():
            logger.info("File already exists: %s", target)
        else:
            await self._download_file_with_progress(download_url, target)

        return target, addon, latest_file

    @staticmethod
    def _select_latest_file(
        addon: CurseAddon, game_version: str = ""
    ) -> AddonFile | None:
        """
        Select the latest non-server-pack file from the addon's ``latestFiles``.

        Optionally filters by ``game_version``. Files are sorted by date
        descending to pick the most recent one.
        """
        candidates = [
            f
            for f in addon.latest_files
            if not f.is_server_pack and f.file_name
        ]
        if game_version:
            filtered = [
                f for f in candidates if game_version in f.game_versions
            ]
            if filtered:
                candidates = filtered

        if not candidates:
            return None

        # Sort by file_date descending (most recent first)
        candidates.sort(
            key=lambda f: f.file_date or datetime.min, reverse=True
        )
        return candidates[0]

    async def _download_file_with_progress(
        self, url: str, target: Path
    ) -> None:
        """Download a single file with a tqdm progress bar showing bytes."""
        async with httpx.AsyncClient(
            timeout=self._download_timeout, follow_redirects=True
        ) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                target.parent.mkdir(parents=True, exist_ok=True)
                pbar = tqdm(
                    total=total or None,
                    desc=target.name,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                )
                with open(target, "wb") as fp:
                    async for chunk in resp.aiter_bytes(8192):
                        fp.write(chunk)
                        pbar.update(len(chunk))
                pbar.close()

    # ── Step 1: Parse manifest ─────────────────────────────────────

    @staticmethod
    def _parse_manifest(zip_path: Path) -> CurseManifest:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # manifest.json is usually at the root of the zip
            for name in zf.namelist():
                if name == "manifest.json" or name.endswith("/manifest.json"):
                    raw = json.loads(zf.read(name))
                    return CurseManifest.model_validate(raw)
        raise FileNotFoundError("No manifest.json found in modpack zip")

    @staticmethod
    def parse_modpack_info(zip_path: str | Path) -> CurseManifest:
        """
        Parse modpack info from a zip file without downloading anything.

        Returns a :class:`CurseManifest` with all locally available info:
        name, version, author, Minecraft version, mod loaders, and the
        list of mod entries (project ID + file ID).

        Usage::

            from curseforge_dl import ModpackInstaller

            manifest = ModpackInstaller.parse_modpack_info("modpack.zip")
            print(manifest.name)                          # "All the Mods 10"
            print(manifest.minecraft.version)              # "1.21.1"
            for loader in manifest.minecraft.mod_loaders:
                print(loader.id)                          # "neoforge-21.1.219"
            print(len(manifest.files))                     # 480
        """
        return ModpackInstaller._parse_manifest(Path(zip_path))

    # ── Step 2: Extract overrides ──────────────────────────────────

    @staticmethod
    def _extract_overrides(
        zip_path: Path, output_dir: Path, overrides_prefix: str
    ) -> int:
        """Extract override files from the zip to the output directory."""
        count = 0
        prefix = overrides_prefix.rstrip("/") + "/"
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if not info.filename.startswith(prefix):
                    continue
                # Relative path inside the game directory
                rel_path = info.filename[len(prefix) :]
                if not rel_path or info.is_dir():
                    continue
                target = output_dir / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                count += 1
        logger.info("Extracted %d override files", count)
        return count

    # ── Step 3: Resolve file names + URLs ──────────────────────────

    async def _resolve_files(
        self,
        files: list[CurseManifestFile],
        progress_callback: Optional[Callable] = None,
    ) -> list[CurseManifestFile]:
        """
        For each file in the manifest, query the API to get the file name
        and download URL if they are missing.
        """
        semaphore = asyncio.Semaphore(self._concurrency)
        resolved: list[CurseManifestFile] = [None] * len(files)  # type: ignore
        total = len(files)
        finished = 0

        pbar = tqdm(total=total, desc="Resolving files", unit="file")

        async def resolve_one(idx: int, f: CurseManifestFile):
            nonlocal finished
            async with semaphore:
                if f.file_name and f.url:
                    resolved[idx] = f
                else:
                    try:
                        addon_file = await self.api.get_mod_file(
                            f.project_id, f.file_id
                        )
                        download_url = addon_file.download_url
                        if not download_url:
                            download_url = build_cdn_url(
                                addon_file.id, addon_file.file_name
                            )
                        resolved[idx] = CurseManifestFile(
                            projectID=f.project_id,
                            fileID=f.file_id,
                            fileName=addon_file.file_name,
                            url=download_url,
                            required=f.required,
                        )
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 404:
                            logger.warning(
                                "File not found: project=%d file=%d (deleted?)",
                                f.project_id,
                                f.file_id,
                            )
                            resolved[idx] = f
                        else:
                            logger.error(
                                "API error for project=%d file=%d: %s",
                                f.project_id,
                                f.file_id,
                                e,
                            )
                            resolved[idx] = f
                    except Exception as e:
                        logger.error(
                            "Failed to resolve project=%d file=%d: %s",
                            f.project_id,
                            f.file_id,
                            e,
                        )
                        resolved[idx] = f
                finished += 1
                pbar.update(1)
                if progress_callback:
                    progress_callback(finished, total, "Resolving file info")

        tasks = [resolve_one(i, f) for i, f in enumerate(files)]
        await asyncio.gather(*tasks)
        pbar.close()

        ok_count = sum(1 for f in resolved if f and f.file_name)
        logger.info("Resolved %d / %d files", ok_count, total)
        return [f for f in resolved if f is not None]

    # ── Step 4: Download files ─────────────────────────────────────

    async def _download_files(
        self,
        files: list[CurseManifestFile],
        output_dir: Path,
        progress_callback: Optional[Callable] = None,
    ) -> None:
        """Download all resolved files to the appropriate directories."""
        downloadable = [f for f in files if f.file_name and f.url]
        if not downloadable:
            logger.warning("No files to download")
            return

        # We need to determine the save path per file. For this we need to
        # know the classId of each project. We batch-query (or cache) as needed.
        file_targets = await self._determine_file_targets(downloadable, output_dir)

        semaphore = asyncio.Semaphore(self._concurrency)
        total = len(file_targets)
        finished = 0

        pbar = tqdm(total=total, desc="Downloading files", unit="file")

        async def download_one(f: CurseManifestFile, target: Path):
            nonlocal finished
            async with semaphore:
                if target.exists():
                    logger.debug("Skipping existing: %s", target.name)
                else:
                    last_error = None
                    for attempt in range(1, self._max_retries + 1):
                        try:
                            await self._download_file(f.url, target)  # type: ignore
                            last_error = None
                            break
                        except Exception as e:
                            last_error = e
                            if attempt < self._max_retries:
                                wait = 2 ** attempt  # exponential backoff: 2, 4, 8...
                                logger.warning(
                                    "Download %s failed (attempt %d/%d): %s — retrying in %ds",
                                    f.file_name, attempt, self._max_retries, e, wait,
                                )
                                # Clean up partial file
                                if target.exists():
                                    target.unlink()
                                await asyncio.sleep(wait)
                    if last_error is not None:
                        logger.error(
                            "Failed to download %s after %d attempts: %s",
                            f.file_name, self._max_retries, last_error,
                        )
                        # Clean up partial file
                        if target.exists():
                            target.unlink()
                finished += 1
                pbar.update(1)
                if progress_callback:
                    progress_callback(finished, total, f"Downloading {f.file_name}")

        tasks = [download_one(f, t) for f, t in file_targets]
        await asyncio.gather(*tasks)
        pbar.close()

        logger.info("Downloaded %d files", total)

    async def _determine_file_targets(
        self,
        files: list[CurseManifestFile],
        output_dir: Path,
    ) -> list[tuple[CurseManifestFile, Path]]:
        """
        Determine the save path for each file based on its project's classId.

        Mirrors ``CurseCompletionTask.guessFilePath()`` in HMCL.
        """
        # Query class IDs in parallel
        semaphore = asyncio.Semaphore(self._concurrency)
        class_ids: dict[int, int] = {}

        async def fetch_class_id(project_id: int):
            async with semaphore:
                try:
                    addon = await self.api.get_mod(project_id)
                    class_ids[project_id] = addon.class_id
                except Exception as e:
                    logger.warning(
                        "Could not get classId for project %d: %s", project_id, e
                    )
                    class_ids[project_id] = SECTION_MOD  # default to mods

        # Deduplicate project IDs
        unique_ids = set(f.project_id for f in files)
        pbar = tqdm(total=len(unique_ids), desc="Querying mod types", unit="mod")

        async def fetch_with_progress(pid: int):
            await fetch_class_id(pid)
            pbar.update(1)

        await asyncio.gather(*[fetch_with_progress(pid) for pid in unique_ids])
        pbar.close()

        # Map classId → subdirectory
        results = []
        for f in files:
            cid = class_ids.get(f.project_id, SECTION_MOD)
            if cid == SECTION_RESOURCE_PACK:
                subdir = "resourcepacks"
            elif cid == SECTION_SHADER_PACK:
                subdir = "shaderpacks"
            else:
                subdir = "mods"
            target = output_dir / subdir / f.file_name  # type: ignore
            target.parent.mkdir(parents=True, exist_ok=True)
            results.append((f, target))

        return results

    async def _download_file(self, url: str, target: Path) -> None:
        """Download a single file with streaming."""
        async with httpx.AsyncClient(
            timeout=self._download_timeout, follow_redirects=True
        ) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as fp:
                    async for chunk in resp.aiter_bytes(8192):
                        fp.write(chunk)
