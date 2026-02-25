"""
CLI entry point for curseforge-dl.

Commands:
  - ``curseforge-dl install <zipfile> <output_dir>``
  - ``curseforge-dl search <query>``
  - ``curseforge-dl info <mod_id>``
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

# Load .env file so CURSEFORGE_API_KEY (and others) can be set via .env
load_dotenv()

from curseforge_dl.api import CurseForgeAPI
from curseforge_dl.installer import ModpackInstaller


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--api-key", envvar="CURSEFORGE_API_KEY", default="", help="CurseForge API key.")
@click.pass_context
def main(ctx: click.Context, verbose: bool, api_key: str) -> None:
    """curseforge-dl: Download mods, resource packs, and shader packs from CurseForge."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["verbose"] = verbose


@main.command()
@click.argument("zipfile", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path())
@click.option("--concurrency", "-c", default=16, help="Max parallel downloads.")
@click.pass_context
def install(ctx: click.Context, zipfile: str, output_dir: str, concurrency: int) -> None:
    """Install a CurseForge modpack from a ZIP file."""
    api_key = ctx.obj["api_key"]
    if not api_key:
        click.echo("Error: CurseForge API key required. Set CURSEFORGE_API_KEY or use --api-key.", err=True)
        sys.exit(1)

    async def run():
        async with CurseForgeAPI(api_key=api_key) as api:
            installer = ModpackInstaller(api, concurrency=concurrency)
            manifest = await installer.install(zipfile, output_dir)
            click.echo(f"\n✓ Installed '{manifest.name}' v{manifest.version}")
            click.echo(f"  Files: {len(manifest.files)}")
            click.echo(f"  Output: {output_dir}")

    asyncio.run(run())


@main.command()
@click.argument("query")
@click.option("--game-version", "-g", default="", help="Minecraft version filter.")
@click.option("--class-id", "-t", default=6, help="Class ID (6=mods, 12=resourcepacks, 4471=modpacks, 6552=shaders).")
@click.option("--limit", "-n", default=10, help="Max results.")
@click.pass_context
def search(ctx: click.Context, query: str, game_version: str, class_id: int, limit: int) -> None:
    """Search for mods on CurseForge."""
    api_key = ctx.obj["api_key"]
    if not api_key:
        click.echo("Error: CurseForge API key required. Set CURSEFORGE_API_KEY or use --api-key.", err=True)
        sys.exit(1)

    async def run():
        async with CurseForgeAPI(api_key=api_key) as api:
            results = await api.search_mods(
                search_filter=query,
                game_version=game_version,
                class_id=class_id,
                page_size=limit,
            )
            if not results:
                click.echo("No results found.")
                return
            for mod in results:
                authors = ", ".join(a.name for a in mod.authors) if mod.authors else "Unknown"
                click.echo(
                    f"  [{mod.id}] {mod.name} by {authors}"
                    f"  — {mod.summary[:80]}..."
                    if len(mod.summary) > 80
                    else f"  [{mod.id}] {mod.name} by {authors}  — {mod.summary}"
                )

    asyncio.run(run())


@main.command()
@click.argument("mod_id", type=int)
@click.pass_context
def info(ctx: click.Context, mod_id: int) -> None:
    """Get detailed info about a CurseForge mod."""
    api_key = ctx.obj["api_key"]
    if not api_key:
        click.echo("Error: CurseForge API key required. Set CURSEFORGE_API_KEY or use --api-key.", err=True)
        sys.exit(1)

    async def run():
        async with CurseForgeAPI(api_key=api_key) as api:
            mod = await api.get_mod(mod_id)
            click.echo(f"Name:       {mod.name}")
            click.echo(f"ID:         {mod.id}")
            click.echo(f"Slug:       {mod.slug}")
            click.echo(f"Summary:    {mod.summary}")
            click.echo(f"Class ID:   {mod.class_id}")
            click.echo(f"Downloads:  {mod.download_count:,}")
            if mod.authors:
                click.echo(f"Authors:    {', '.join(a.name for a in mod.authors)}")
            if mod.links and mod.links.website_url:
                click.echo(f"URL:        {mod.links.website_url}")
            click.echo(f"Categories: {', '.join(c.name for c in mod.categories)}")
            click.echo(f"\nLatest files ({len(mod.latest_files)}):")
            for f in mod.latest_files[:5]:
                click.echo(f"  [{f.id}] {f.display_name}  ({f.file_name})")

    asyncio.run(run())


@main.command("modpack-info")
@click.argument("zipfile", type=click.Path(exists=True))
@click.option("--show-mods", "-m", is_flag=True, help="Show full mod list with project/file IDs.")
def modpack_info(zipfile: str, show_mods: bool) -> None:
    """Parse and display modpack information from a ZIP file (no download needed)."""
    from curseforge_dl.installer import ModpackInstaller

    try:
        manifest = ModpackInstaller._parse_manifest(Path(zipfile))
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    mc = manifest.minecraft

    click.echo("=" * 50)
    click.echo(f"  Modpack:    {manifest.name}")
    click.echo(f"  Version:    {manifest.version}")
    click.echo(f"  Author:     {manifest.author}")
    click.echo("=" * 50)
    click.echo(f"  Minecraft:  {mc.version}")

    for loader in mc.mod_loaders:
        # Loader id is like "neoforge-21.1.90" or "forge-47.2.0"
        parts = loader.id.split("-", 1)
        loader_name = parts[0] if parts else loader.id
        loader_version = parts[1] if len(parts) > 1 else "unknown"
        primary = " (primary)" if loader.primary else ""
        click.echo(f"  Loader:     {loader_name} {loader_version}{primary}")

    click.echo(f"  Overrides:  {manifest.overrides}")
    click.echo(f"  Total mods: {len(manifest.files)}")
    click.echo("=" * 50)

    if show_mods or len(manifest.files) <= 20:
        click.echo("\n  Mod list:")
        for i, f in enumerate(manifest.files, 1):
            required = "" if f.required else " (optional)"
            click.echo(f"    {i:>4}. project={f.project_id}  file={f.file_id}{required}")
    elif not show_mods:
        click.echo(f"\n  (Use --show-mods / -m to list all {len(manifest.files)} mods)")


@main.command()
@click.argument("slug")
@click.option("--game-version", "-g", default="", help="Minecraft version filter.")
@click.pass_context
def fetch(ctx: click.Context, slug: str, game_version: str) -> None:
    """Fetch and display modpack info by its slug (e.g. 'all-the-mods-10')."""
    api_key = ctx.obj["api_key"]
    if not api_key:
        click.echo("Error: CurseForge API key required. Set CURSEFORGE_API_KEY or use --api-key.", err=True)
        sys.exit(1)

    async def run():
        async with CurseForgeAPI(api_key=api_key) as api:
            from curseforge_dl.models import SECTION_MODPACK

            addon = await api.get_mod_by_slug(slug, class_id=SECTION_MODPACK)
            if addon is None:
                click.echo(f"Error: Modpack '{slug}' not found.", err=True)
                sys.exit(1)

            authors = ", ".join(a.name for a in addon.authors) if addon.authors else "Unknown"
            click.echo("=" * 55)
            click.echo(f"  Modpack:     {addon.name}")
            click.echo(f"  ID:          {addon.id}")
            click.echo(f"  Slug:        {addon.slug}")
            click.echo(f"  Authors:     {authors}")
            click.echo(f"  Summary:     {addon.summary}")
            click.echo(f"  Downloads:   {addon.download_count:,}")
            if addon.links and addon.links.website_url:
                click.echo(f"  URL:         {addon.links.website_url}")
            click.echo("=" * 55)

            # Show latest files
            installer = ModpackInstaller(api)
            latest = installer._select_latest_file(addon, game_version)
            if latest:
                click.echo(f"\n  Latest file:")
                click.echo(f"    Name:      {latest.display_name or latest.file_name}")
                click.echo(f"    File:      {latest.file_name}")
                click.echo(f"    File ID:   {latest.id}")
                if latest.file_length:
                    size_mb = latest.file_length / 1024 / 1024
                    click.echo(f"    Size:      {size_mb:.1f} MB")
                if latest.file_date:
                    click.echo(f"    Date:      {latest.file_date.strftime('%Y-%m-%d %H:%M')}")
                if latest.game_versions:
                    click.echo(f"    Versions:  {', '.join(latest.game_versions)}")
                release_types = {1: "Release", 2: "Beta", 3: "Alpha"}
                click.echo(f"    Type:      {release_types.get(latest.release_type, 'Unknown')}")
            else:
                click.echo("\n  No downloadable files found.")

            if len(addon.latest_files) > 1:
                click.echo(f"\n  All latest files ({len(addon.latest_files)}):")
                for f in addon.latest_files:
                    server = " [server]" if f.is_server_pack else ""
                    click.echo(f"    [{f.id}] {f.display_name or f.file_name}{server}")

    asyncio.run(run())


@main.command()
@click.argument("slug")
@click.option("--output-dir", "-o", default=".", type=click.Path(), help="Output directory (default: current dir).")
@click.option("--game-version", "-g", default="", help="Minecraft version filter.")
@click.pass_context
def download(ctx: click.Context, slug: str, output_dir: str, game_version: str) -> None:
    """Download the latest modpack zip by its slug (e.g. 'all-the-mods-10')."""
    api_key = ctx.obj["api_key"]
    if not api_key:
        click.echo("Error: CurseForge API key required. Set CURSEFORGE_API_KEY or use --api-key.", err=True)
        sys.exit(1)

    async def run():
        async with CurseForgeAPI(api_key=api_key) as api:
            installer = ModpackInstaller(api)
            try:
                zip_path, addon, file_info = await installer.download_modpack_by_slug(
                    slug, output_dir=output_dir, game_version=game_version
                )
                click.echo(f"\n✓ Downloaded '{addon.name}'")
                click.echo(f"  File:   {file_info.display_name or file_info.file_name}")
                click.echo(f"  Saved:  {zip_path}")
                if file_info.file_length:
                    click.echo(f"  Size:   {file_info.file_length / 1024 / 1024:.1f} MB")
            except ValueError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()
