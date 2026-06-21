#!/usr/bin/env python3
"""
album-renamer — Standardize music album folder names to 'Artist - Album' format.
Parses folder names, scans audio file metadata, and interactively renames.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# ── constants ──────────────────────────────────────────────────────────────────

AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".wma", ".aiff", ".opus"}

SKIP_EXTENSIONS = {".zip", ".rar", ".7z", ".flac", ".mp3", ".m4a", ".wav", ".ogg", ".mkv", ".avi", ".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".pdf", ".nfo", ".sfv", ".m3u", ".cue", ".log", ".txt", ".url", ".md5", ".st5", ".accurip"}

SKIP_FOLDER_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^disc\s*\d+$",
        r"^vol(?:ume)?[\s\.]?\d+$",
        r"^cd\s*\d+$",
        r"^part\s*\d+$",
        r"^side\s*[a-d]$",
        r"^scans?$",
        r"^artwork$",
        r"^covers?$",
        r"^extras?$",
        r"^bonus\s*(?:disc|cd|tracks?)?$",
    ]
]

ROLLBACK_FILE = Path.home() / ".album_renamer_rollback.json"

FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*]')

# ── name parsing patterns ──────────────────────────────────────────────────────
# Each entry: (regex, has_artist)
#   has_artist=True  → artist group present
#   has_artist=False → artist is None (metadata needed)
#   has_artist=None  → ambiguous (treat as album-only)
NAME_PATTERNS = [
    # 1. [format] Artist -- Album [...extra]
    (re.compile(r"^\[.*?\]\s+(?P<artist>.+?)\s*--\s+(?P<album>.+?)(?:\s*\[.*?\])?\s*$"), True),
    # 2. Artist - Album (Year) ...
    (re.compile(r"^(?P<artist>.+?)\s*-\s+(?P<album>.+?)\s*\(\d{4}(?:[^)]*)\)"), True),
    # 3. Artist - Album [Year] ...
    (re.compile(r"^(?P<artist>.+?)\s*-\s+(?P<album>.+?)\s*\[\d{4}\]"), True),
    # 4. Artist - [Year] Album
    (re.compile(r"^(?P<artist>.+?)\s*-\s*\[\d{4}\]\s+(?P<album>.+?)$"), True),
    # 5. Artist - Year - Album
    (re.compile(r"^(?P<artist>.+?)\s*-\s*\d{4}\s*-\s+(?P<album>.+?)$"), True),
    # 6. Artist - Album (generic — must come last among "has_artist" patterns)
    (re.compile(r"^(?P<artist>.+?)\s*-\s+(?P<album>.+?)(?:\s*[\(\{\[].*)?\s*$"), True),
    # 7. (Year) Album   (no artist)
    (re.compile(r"^[\(\[](\d{4})[\)\]]\s+(?P<album>.+?)\s*$"), False),
    # 8. [Year] Artist Album stuff  → not enough info, treat as unknown
    (re.compile(r"^\[\d{4}\]\s+(?P<album>.+?)\s*$"), False),
    # 9. Year - Album   (no artist)
    (re.compile(r"^\d{4}\s*-\s+(?P<album>.+?)\s*$"), False),
    # 10. Album (Year)   (no artist)
    (re.compile(r"^(?P<album>.+?)\s*\(\d{4}\)\s*$"), False),
    # 11. Just a name   (ambiguous — could be album or artist)
    (re.compile(r"^(?P<album>.+?)\s*$"), None),
]


def should_skip_folder(entry: Path) -> bool:
    """Check whether a directory entry should be ignored."""
    if not entry.is_dir():
        return True
    name = entry.name.strip()
    for pattern in SKIP_FOLDER_PATTERNS:
        if pattern.fullmatch(name):
            return True
    return False


def is_already_correct_format(name: str) -> bool:
    """
    Check if a folder name is already EXACTLY in 'Artist - Album' format
    with no year or format extras that need stripping.
    """
    if " - " not in name:
        return False

    # If the raw name contains year brackets/parens, it needs cleaning
    if re.search(r"[\(\{\[](?:\b(?:19|20)\d{2}\b)[\)\}\]]", name):
        return False

    # If the raw name contains format tags like [FLAC], (V0), etc.
    if re.search(
        r"[\(\{\[]\s*(?:FLAC|MP3|V0|V2|V\d|320|Kbps|kHz|EAC|WEB|Lossless|CD)\s*[\)\}\]]",
        name,
        re.IGNORECASE,
    ):
        return False

    # If a year sits between dashes: Artist - 2015 - Album
    if re.search(r"-\s*(?:19|20)\d{2}\s*-", name):
        return False

    # Must have exactly one clean ' - ' that splits artist and album
    parts = name.split(" - ", 1)
    if len(parts) != 2:
        return False
    artist, _album = parts
    artist = artist.strip()
    if not artist:
        return False
    if re.match(r"^\d{4}$", artist):
        return False
    if re.match(r"^\[.*\]$", artist):
        return False

    return True


def parse_folder_name(name: str) -> tuple[str | None, str]:
    """
    Parse a folder name into (artist, album).
    Returns (None, album) if artist could not be determined.
    """
    name = name.strip()
    for pattern, has_artist in NAME_PATTERNS:
        m = pattern.match(name)
        if m:
            album = m.group("album").strip()
            if has_artist is True:
                artist = m.group("artist").strip()
                if artist and not re.match(r"^\d{4}$", artist):
                    return (artist, album)
            elif has_artist is False:
                return (None, album)
            else:
                return (None, album)
    return (None, name)


def clean_album_name(raw: str) -> str:
    """Remove format tags, catalog numbers, and trailing punctuation from an album name."""
    raw = raw.strip()
    raw = re.sub(r"\s*\[\s*[^\]]*?\s*\]\s*$", "", raw)
    raw = re.sub(r"\s*\{\s*[^}]*?\s*\}\s*$", "", raw)
    raw = re.sub(r"\s*\(\s*\d{4}[^)]*\)\s*$", "", raw)
    raw = re.sub(r"\s*\(\s*(?:FLAC|MP3|V0|320|Lossless|WEB)\s*\)\s*$", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s{2,}", " ", raw)
    raw = raw.strip().rstrip(".-_ ")
    return raw


def safe_filename(name: str) -> str:
    return FORBIDDEN_CHARS.sub("", name)


# ── metadata scanning ──────────────────────────────────────────────────────────


def _get_artist_tag(filepath: Path) -> str | None:
    """Extract artist tag from a single audio file."""
    ext = filepath.suffix.lower()
    try:
        if ext == ".flac":
            from mutagen.flac import FLAC

            audio = FLAC(filepath)
            return audio.get("artist", [None])[0]
        elif ext == ".mp3":
            from mutagen.mp3 import MP3

            audio = MP3(filepath)
            for tag_id in ("TPE1", "TPE2", "TPE3"):
                val = str(audio.get(tag_id, [""])[0])
                if val:
                    return val
            return None
        elif ext in (".m4a", ".mp4", ".m4b"):
            from mutagen.mp4 import MP4

            audio = MP4(filepath)
            return audio.get("\xa9ART", [None])[0] or audio.get("aART", [None])[0]
        elif ext == ".ogg":
            from mutagen.oggvorbis import OggVorbis

            audio = OggVorbis(filepath)
            return audio.get("artist", [None])[0]
        elif ext in (".wav", ".wma"):
            try:
                from mutagen.wave import WAVE

                audio = WAVE(filepath)
                if audio.tags:
                    return str(audio.tags.get("TPE1", [""])[0]) or None
            except Exception:
                pass
    except Exception:
        pass
    return None


def scan_folder_artist(folder: Path) -> str | None:
    """Scan all audio files recursively and return the most common artist tag."""
    artists: list[str] = []
    for f in folder.rglob("*"):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
            artist = _get_artist_tag(f)
            if artist and artist.strip().lower() not in (
                "various artists",
                "various",
                "unknown",
                "unknown artist",
            ):
                artists.append(artist.strip())
    if not artists:
        return None
    return Counter(artists).most_common(1)[0][0]


def bulk_scan_artists(base_dir: Path, folders: list[Path]) -> dict[Path, str | None]:
    """Pre-scan multiple folders for artist metadata."""
    results: dict[Path, str | None] = {}
    total = len(folders)
    for i, folder in enumerate(folders, 1):
        print(f"  [{i}/{total}] scanning: {folder.name}")
        results[folder] = scan_folder_artist(folder)
    return results


# ── rename engine ──────────────────────────────────────────────────────────────


def execute_renames(renames: list[tuple[Path, str]]) -> list[dict]:
    rollback: list[dict] = []
    for folder, new_name in renames:
        parent = folder.parent
        new_path = parent / new_name
        if new_path.exists():
            print(f"  SKIP (exists): {folder.name} → {new_name}")
            continue
        try:
            folder.rename(new_path)
            rollback.append(
                {
                    "original": str(folder),
                    "new": str(new_path),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            print(f"  OK: {folder.name} → {new_name}")
        except OSError as e:
            print(f"  FAIL: {folder.name} → {new_name}  ({e})")
    with open(ROLLBACK_FILE, "w") as f:
        json.dump(rollback, f, indent=2)
    return rollback


def undo_last_run() -> int:
    if not ROLLBACK_FILE.exists():
        print("No rollback file found.")
        return 0
    with open(ROLLBACK_FILE) as f:
        records = json.load(f)
    restored = 0
    for rec in reversed(records):
        original = Path(rec["original"])
        new_path = Path(rec["new"])
        if new_path.exists():
            try:
                new_path.rename(original)
                print(f"  UNDO: {new_path.name} → {original.name}")
                restored += 1
            except OSError as e:
                print(f"  UNDO FAIL: {new_path.name}  ({e})")
    ROLLBACK_FILE.unlink()
    print(f"Restored {restored} folder(s).")
    return restored


# ── main ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standardize music album folder names to 'Artist - Album' format."
    )
    parser.add_argument(
        "target_dir",
        nargs="?",
        help="Path to the directory containing album subfolders.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without renaming (default).",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Execute renames (requires confirmation).",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the last rename session using the rollback file.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip interactive confirmation (auto-approve).",
    )
    parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="Skip scanning audio file metadata for missing artists.",
    )

    args = parser.parse_args()

    if args.undo:
        undo_last_run()
        return

    target = Path(args.target_dir) if args.target_dir else None
    if not target:
        print("Error: target_dir is required.")
        sys.exit(1)
    if not target.is_dir():
        print(f"Error: '{target}' is not a directory or does not exist.")
        sys.exit(1)

    print(f"Scanning: {target}\n")

    entries = sorted(target.iterdir())
    folders = [p for p in entries if not should_skip_folder(p)]

    print(f"Found {len(folders)} subfolder(s) to analyze.\n")

    # ── phase 1: parse every folder name ──
    parsed: list[dict] = []
    need_metadata: list[Path] = []

    for folder in folders:
        name = folder.name
        if is_already_correct_format(name):
            print(f"  SKIP (already correct): {name}")
            parsed.append({"folder": folder, "artist": None, "album": name, "reason": "already_correct"})
            continue

        artist, album = parse_folder_name(name)
        album = clean_album_name(album)

        if artist and artist.strip().lower() in ("various artists", "various"):
            parsed.append({"folder": folder, "artist": artist.strip(), "album": album, "reason": "various_artists"})
        elif artist:
            parsed.append({"folder": folder, "artist": artist.strip(), "album": album, "reason": None})
        else:
            need_metadata.append(folder)
            parsed.append({"folder": folder, "artist": None, "album": album, "reason": "need_metadata"})

    # ── phase 2: metadata scan ──
    if need_metadata and not args.skip_metadata:
        print(f"\nScanning audio metadata for {len(need_metadata)} folder(s)...\n")
        meta = bulk_scan_artists(target, need_metadata)
        for i, entry in enumerate(parsed):
            if entry["reason"] == "need_metadata":
                artist = meta.get(entry["folder"])
                if artist:
                    parsed[i]["artist"] = artist
                    parsed[i]["reason"] = None
                    print(f"  resolved via metadata: {entry['folder'].name} → artist='{artist}'")
                else:
                    parsed[i]["reason"] = "no_metadata"
                    print(f"  no metadata found: {entry['folder'].name}")

    # ── phase 3: build rename list + unresolved ──
    renames: list[tuple[Path, str]] = []
    unresolved: list[dict] = []

    for entry in parsed:
        if entry["reason"] == "already_correct":
            continue
        artist = entry.get("artist")
        album = entry.get("album", "")

        if artist:
            new_name = safe_filename(f"{artist} - {album}")
            if new_name == entry["folder"].name:
                print(f"  already matches: {new_name}")
                continue
            renames.append((entry["folder"], new_name))
        else:
            unresolved.append(entry)

    # ── phase 4: handle unresolved ──
    if unresolved:
        if args.yes:
            print(f"\n─── {len(unresolved)} unresolved folder(s) (auto-skipped with --yes) ───\n")
            for entry in unresolved:
                print(f"  ? {entry['folder'].name}  (reason: {entry.get('reason', 'unknown')})")
        else:
            print(f"\n─── {len(unresolved)} unresolved folder(s) ───\n")
            for entry in unresolved:
                folder = entry["folder"]
                album = entry.get("album", folder.name)
                reason = entry.get("reason", "unknown")
                print(f"  ? {folder.name}")
                print(f"     album : {album}")
                print(f"     reason: {reason}")
                choice = input("     artist? (enter name, 's'=skip, 'q'=quit): ").strip()
                if choice.lower() == "q":
                    break
                if choice.lower() == "s":
                    continue
                if choice:
                    new_name = safe_filename(f"{choice} - {album}")
                    renames.append((folder, new_name))

    # ── phase 5: preview + execute ──
    if not renames:
        print("\nNo renames needed.")
        return

    print(f"\n─── Proposed renames ({len(renames)}) ───\n")
    for folder, new_name in renames:
        print(f"  {folder.name}")
        print(f"  → {new_name}\n")

    if args.dry_run:
        print("[dry run] No changes made. Add --no-dry-run to execute.")
        return

    if not args.yes:
        confirm = input("Execute these renames? (y/N): ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    print()
    rollback = execute_renames(renames)
    print(f"\nDone. {len(rollback)} folder(s) renamed.")
    print(f"Undo with: album_renamer --undo")


if __name__ == "__main__":
    main()
