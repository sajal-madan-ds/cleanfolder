"""Folder scanner — recursively walks a directory and collects file metadata."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from cleanfolder.utils import (
    FileInfo,
    FolderInfo,
    file_created_time,
    file_modified_time,
    format_size,
    get_mime_type,
)


def scan_folder(
    target: Path,
    *,
    skip_hidden: bool = True,
    skip_patterns: list[str] | None = None,
    max_files: int = 10_000,
    show_progress: bool = True,
) -> list[FileInfo]:
    """
    Recursively scan *target* and return a list of FileInfo objects.

    Hashes are computed lazily (only on first access) so scanning stays fast.
    """
    if not target.is_dir():
        raise NotADirectoryError(f"Target is not a directory: {target}")

    skip_patterns = skip_patterns or [
        ".DS_Store", "__MACOSX", "Thumbs.db", ".localized",
        "twingate*", "jumpcloud*", "freshservice*", "com.apple.*",
    ]

    all_paths = _collect_paths(target, skip_hidden=skip_hidden, skip_patterns=skip_patterns)

    if len(all_paths) > max_files:
        raise RuntimeError(
            f"Folder contains {len(all_paths)} files (limit: {max_files}). "
            "Pass --max-files to increase the limit."
        )

    files: list[FileInfo] = []

    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Scanning"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[dim]{task.description}"),
        ) as progress:
            task = progress.add_task("", total=len(all_paths))
            for p in all_paths:
                info = _build_file_info(p)
                if info is not None:
                    files.append(info)
                progress.update(task, advance=1, description=p.name[:40])
    else:
        for p in all_paths:
            info = _build_file_info(p)
            if info is not None:
                files.append(info)

    return files


def _collect_paths(
    root: Path,
    *,
    skip_hidden: bool,
    skip_patterns: list[str],
) -> list[Path]:
    """Walk the directory tree and collect file paths, respecting skip rules."""
    paths: list[Path] = []
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        if skip_hidden and any(part.startswith(".") for part in entry.relative_to(root).parts):
            continue
        if any(fnmatch.fnmatch(entry.name, pat) for pat in skip_patterns):
            continue
        paths.append(entry)
    return paths


def scan_subfolders(
    target: Path,
    *,
    skip_hidden: bool = True,
) -> list[FolderInfo]:
    """
    Scan immediate subdirectories of *target* and return FolderInfo objects.

    Computes file count and total size for each subfolder (recursively).
    """
    folders: list[FolderInfo] = []
    try:
        entries = sorted(target.iterdir())
    except PermissionError:
        return []

    for entry in entries:
        if not entry.is_dir():
            continue
        if skip_hidden and entry.name.startswith("."):
            continue

        file_count = 0
        total_size = 0
        try:
            for child in entry.rglob("*"):
                if child.is_file():
                    file_count += 1
                    try:
                        total_size += child.stat().st_size
                    except OSError:
                        pass
        except PermissionError:
            pass

        folders.append(FolderInfo(
            name=entry.name,
            path=entry,
            file_count=file_count,
            total_size=total_size,
            is_empty=(file_count == 0),
            modified=file_modified_time(entry),
        ))

    return folders


def _build_file_info(path: Path) -> FileInfo | None:
    """Build a FileInfo from a path, returning None if the file is unreadable."""
    try:
        stat = path.stat()
        return FileInfo(
            name=path.name,
            path=path,
            size=stat.st_size,
            extension=path.suffix.lower(),
            mime_type=get_mime_type(path),
            created=file_created_time(path),
            modified=file_modified_time(path),
        )
    except (OSError, PermissionError):
        return None
