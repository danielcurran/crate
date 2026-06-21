---
name: crate
description: Crate — standardize messy music album folder names into clean Artist - Album format, like pulling records from a crate
license: MIT
---

## What this skill does

Pulls album folders out of the mess and onto the shelf. Renames subfolders to `Artist - Album`. Handles chaos like:

- `[flac] Sid Frank -- Beijing 1988 [Zoomin' Night, 2024]`
- `billy woods - 2015 - today, i wrote nothing`
- `Billy Woods - Known Unknowns (2017) [FLAC]`
- `[2020] NIOH 2 Original Soundtrack [KECH-1954~5]`
- `1975 Coney Island Baby`
- `(2023) Soon`

All become `Artist - Album`.

## Prerequisites

- Python 3.8+
- `mutagen` library for audio metadata scanning

## Setup (first use)

```bash
cd ~/repos/crate
python3 -m venv venv && source venv/bin/activate && pip install mutagen
```

## Usage workflow

1. **Ask the user** which directory to scan (the parent folder containing album subfolders).
2. **Always run dry-run first** and show the results:
   ```bash
   cd ~/repos/crate && source venv/bin/activate
   python crate.py "/path/to/music" --dry-run
   ```
3. **Show the proposed renames** to the user. Let them review.
4. For any **unresolved folders** (artist unknown, no metadata), ask the user what to do or use your own knowledge to suggest the correct artist.
5. Once the user approves, **execute**:
   ```bash
   python crate.py "/path/to/music" --no-dry-run
   ```

## What the script handles automatically

- Skips folders already in `Artist - Album` format
- Skips `Disc 1`, `Volume 1`, `CD 1`, covers/scans folders
- Skips individual audio/video files and zip archives
- Parses 10+ common naming patterns
- Scans audio file metadata (FLAC, MP3, M4A, OGG, WAV) for artist tags
- Cleans format tags like `[FLAC]`, `[V0]`, catalog numbers from album names
- Removes years from album names
- Preserves original casing (billy woods stays billy woods)
- Creates a rollback file for undo

## Edge cases needing your intervention

- **Single-word folder names** with no metadata (e.g., "Goat", "Melodrama") — use your knowledge to suggest the artist
- **Live recordings** with dates in the name (e.g., `tinariwen - 2004 11 08 - cultural center, chicago [flac]`) — flag for user review
- **Multi-artist with hyphens** in artist name (e.g., `Matt Sweeney & Bonnie -Prince- Billy - Superwolves`) — verify parse is correct
- **Various Artists compilations** — kept as-is by default

## Safety

- Never rename without a dry-run first
- Remind the user to back up their music directory before executing
- The rollback file is at `~/.crate_rollback.json`
- Undo with: `python crate.py --undo`

## Important

- Do NOT rename folders unless the user explicitly confirms after reviewing the dry-run output
- Output format is exactly `Artist - Album` (no year, no format tags)
- Preserve the original casing of artist and album names
