# curseforge-dl

A Python package to download mods, resource packs, and shader packs from CurseForge.
Replicates the download logic used by [HMCL](https://github.com/HMCL-dev/HMCL).

## Installation

```bash
pip install curseforge-dl
```

## Usage

### CLI

```bash
# Set your CurseForge API key (choose one method):

# Method 1: Create a .env file (recommended)
cp .env.example .env
# Edit .env and set CURSEFORGE_API_KEY=your-key

# Method 2: Environment variable
export CURSEFORGE_API_KEY="your-api-key"

# Method 3: Pass directly via CLI
curseforge-dl --api-key "your-api-key" install modpack.zip ./output

# Install a CurseForge modpack
curseforge-dl install modpack.zip ./output

# Search for mods
curseforge-dl search "JEI" --game-version 1.21.1

# Get mod info
curseforge-dl info 238222

# Parse modpack info (no API key / download needed)
curseforge-dl modpack-info modpack.zip

# Parse modpack info with full mod list
curseforge-dl modpack-info modpack.zip --show-mods
```

### Python API

```python
import asyncio
from curseforge_dl import CurseForgeAPI, ModpackInstaller

async def main():
    async with CurseForgeAPI(api_key="your-key") as api:
        # Search mods
        results = await api.search_mods("JEI", game_version="1.21.1")
        for mod in results:
            print(mod.name)

        # Install a modpack
        installer = ModpackInstaller(api)
        await installer.install("modpack.zip", "./output")

asyncio.run(main())
```

### Parse modpack info (no API key needed)

```python
from curseforge_dl import ModpackInstaller

manifest = ModpackInstaller.parse_modpack_info("modpack.zip")

print(manifest.name)                          # "All the Mods 10"
print(manifest.version)                       # "5.5"
print(manifest.author)                        # "ATMTeam"
print(manifest.minecraft.version)             # "1.21.1"

for loader in manifest.minecraft.mod_loaders:
    print(loader.id)                          # "neoforge-21.1.219"

print(f"Total mods: {len(manifest.files)}")   # 480
```

## Features

- **Modpack installation**: Parse CurseForge modpack zips and download all mods
- **Modpack info**: Parse modpack metadata (MC version, loader, mod list) without downloading
- **Smart URL construction**: Falls back to CDN URL when API doesn't provide download links
- **File fingerprinting**: MurmurHash2-based local file matching
- **Async downloads**: Parallel downloads with configurable concurrency
- **Download retry**: Automatic retry with exponential backoff on failure (default 3 attempts)
- **Progress reporting**: Built-in tqdm progress bars

## License

MIT
