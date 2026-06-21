# crate

Pull your music library out of the mess and onto the shelf.

Standardizes album folder names to `Artist - Album` format. Parses folder names, scans audio file metadata, and interactively renames — like pulling records from a crate and filing them properly.

## Install

```bash
git clone https://github.com/danielcurran/crate.git
cd crate
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Usage

Always dry-run first:

```bash
python crate.py "/path/to/music" --dry-run
```

Review the proposed changes, then execute:

```bash
python crate.py "/path/to/music" --no-dry-run
```

Undo your last rename session:

```bash
python crate.py --undo
```

## What it does

| Before | After |
|---|---|
| `[flac] Sid Frank -- Beijing 1988 [Zoomin' Night, 2024]` | `Sid Frank - Beijing 1988` |
| `billy woods - 2015 - today, i wrote nothing` | `billy woods - today, i wrote nothing` |
| `Billy Woods - Known Unknowns (2017) [FLAC]` | `Billy Woods - Known Unknowns` |
| `(2023) Soon` | `Artist From Metadata - Soon` |
| `1975 Coney Island Baby` | prompted or metadata-sourced |

- Skips folders already in `Artist - Album` format
- Skips `Disc 1`, `Volume 2`, `CD 3`, covers/scans folders
- Skips individual audio/video files and archives
- Reads artist tags from FLAC, MP3, M4A, OGG, WAV
- Prompts interactively for anything it can't figure out

## CLI flags

| Flag | Effect |
|---|---|
| `--dry-run` | Preview only (default) |
| `--no-dry-run` | Execute renames |
| `--undo` | Restore previous renames |
| `--yes` / `-y` | Skip prompts, auto-approve |
| `--skip-metadata` | Don't scan audio file tags |

## OpenCode skill

## OpenCode agent skill

Crate ships with an agent skill so [OpenCode](https://opencode.ai) can run it for you.

**Auto-discovered** — run opencode from this repo directory and the skill is available immediately (ships at `.opencode/skills/crate/SKILL.md`).

**Global install** — to use from any directory:

```bash
mkdir -p ~/.config/opencode/skills/crate
cp .opencode/skills/crate/SKILL.md ~/.config/opencode/skills/crate/SKILL.md
```

## Requirements

- Python 3.8+
- [mutagen](https://mutagen.readthedocs.io/)
