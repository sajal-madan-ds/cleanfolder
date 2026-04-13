"""Action executor — trash, archive, organize files with safety guardrails."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from cleanfolder.analyzer import AnalysisResult
from cleanfolder.duplicates import DuplicateGroup
from cleanfolder.utils import FileInfo, FolderInfo, format_size

console = Console()


def trash_duplicates(
    groups: list[DuplicateGroup],
    *,
    dry_run: bool = True,
) -> list[Path]:
    """
    Move duplicate files to macOS Trash, keeping the recommended file per group.

    Returns the list of paths that were (or would be) trashed.
    """
    from send2trash import send2trash

    to_trash: list[Path] = []
    for group in groups:
        for f in group.files:
            if f is not group.recommended_keep:
                to_trash.append(f.path)

    if not to_trash:
        console.print("[dim]No duplicate files to trash.[/dim]")
        return []

    total_size = sum(p.stat().st_size for p in to_trash if p.exists())

    table = Table(title="Files to Trash", show_lines=True)
    table.add_column("File", style="red")
    table.add_column("Size", justify="right")
    for p in to_trash:
        sz = format_size(p.stat().st_size) if p.exists() else "?"
        table.add_row(str(p), sz)
    console.print(table)
    console.print(f"\n[bold]Total reclaimable:[/bold] {format_size(total_size)} across {len(to_trash)} files")

    if dry_run:
        console.print("[yellow]Dry run — no files were moved. Use --execute to apply.[/yellow]")
        return to_trash

    if not click.confirm("Move these files to Trash?"):
        console.print("[dim]Cancelled.[/dim]")
        return []

    trashed: list[Path] = []
    for p in to_trash:
        try:
            send2trash(str(p))
            trashed.append(p)
        except Exception as e:
            console.print(f"[red]Failed to trash {p.name}: {e}[/red]")

    console.print(f"[green]Moved {len(trashed)} files to Trash.[/green]")
    return trashed


def trash_temp_files(
    temp_files: list[FileInfo],
    *,
    dry_run: bool = True,
) -> list[Path]:
    """Move temporary/incomplete files to Trash."""
    from send2trash import send2trash

    if not temp_files:
        console.print("[dim]No temporary files found.[/dim]")
        return []

    paths = [f.path for f in temp_files]
    total_size = sum(f.size for f in temp_files)

    table = Table(title="Temporary Files to Trash", show_lines=True)
    table.add_column("File", style="red")
    table.add_column("Size", justify="right")
    for f in temp_files:
        table.add_row(str(f.path), format_size(f.size))
    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {format_size(total_size)} across {len(paths)} files")

    if dry_run:
        console.print("[yellow]Dry run — no files were moved. Use --execute to apply.[/yellow]")
        return paths

    if not click.confirm("Move these temporary files to Trash?"):
        console.print("[dim]Cancelled.[/dim]")
        return []

    trashed: list[Path] = []
    for p in paths:
        try:
            send2trash(str(p))
            trashed.append(p)
        except Exception as e:
            console.print(f"[red]Failed to trash {p.name}: {e}[/red]")

    console.print(f"[green]Moved {len(trashed)} temp files to Trash.[/green]")
    return trashed


def archive_files(
    files: list[FileInfo],
    archive_path: Path,
    *,
    dry_run: bool = True,
    delete_originals: bool = False,
) -> Path | None:
    """Compress a list of files into a zip archive."""
    from send2trash import send2trash

    if not files:
        console.print("[dim]No files to archive.[/dim]")
        return None

    total_size = sum(f.size for f in files)
    console.print(
        f"[bold]Archiving {len(files)} files ({format_size(total_size)}) "
        f"→ {archive_path.name}[/bold]"
    )

    if dry_run:
        console.print("[yellow]Dry run — archive not created. Use --execute to apply.[/yellow]")
        return archive_path

    if archive_path.exists() and not click.confirm(f"{archive_path.name} already exists. Overwrite?"):
        return None

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f.path, f.name)

    console.print(f"[green]Created {archive_path.name} ({format_size(archive_path.stat().st_size)})[/green]")

    if delete_originals:
        if click.confirm("Delete originals after archiving?"):
            for f in files:
                try:
                    send2trash(str(f.path))
                except Exception as e:
                    console.print(f"[red]Failed to trash {f.name}: {e}[/red]")

    return archive_path


def trash_empty_folders(
    empty_folders: list[FolderInfo],
    *,
    dry_run: bool = True,
) -> list[Path]:
    """Remove empty folders (directories with zero files)."""
    from send2trash import send2trash

    if not empty_folders:
        console.print("[dim]No empty folders found.[/dim]")
        return []

    table = Table(title="Empty Folders to Remove", show_lines=True)
    table.add_column("Folder", style="red")
    table.add_column("Modified", style="dim")
    for f in empty_folders:
        table.add_row(f"{f.name}/", f"{f.modified:%Y-%m-%d}")
    console.print(table)
    console.print(f"\n[bold]{len(empty_folders)} empty folder(s)[/bold]")

    if dry_run:
        console.print("[yellow]Dry run — no folders were removed. Use --execute to apply.[/yellow]")
        return [f.path for f in empty_folders]

    if not click.confirm("Move these empty folders to Trash?"):
        console.print("[dim]Cancelled.[/dim]")
        return []

    trashed: list[Path] = []
    for f in empty_folders:
        try:
            send2trash(str(f.path))
            trashed.append(f.path)
        except Exception as e:
            console.print(f"[red]Failed to trash {f.name}/: {e}[/red]")

    console.print(f"[green]Moved {len(trashed)} empty folder(s) to Trash.[/green]")
    return trashed


def organize_files(
    result: AnalysisResult,
    *,
    dry_run: bool = True,
) -> dict[str, list[Path]]:
    """
    Move files into categorized subdirectories within the target folder.

    Creates folders like Images/, Documents/, Videos/ etc.
    """
    moves: dict[str, list[Path]] = {}

    for category, files in result.categories.by_category.items():
        if category == "Other":
            continue
        dest_dir = result.target / category
        for f in files:
            if f.path.parent == result.target:
                moves.setdefault(category, []).append(f.path)

    if not moves:
        console.print("[dim]No files to organize (all already in subdirectories).[/dim]")
        return {}

    total_files = sum(len(paths) for paths in moves.values())
    table = Table(title="Organization Plan", show_lines=True)
    table.add_column("Category", style="bold")
    table.add_column("Files", justify="right")
    for cat, paths in sorted(moves.items()):
        table.add_row(cat, str(len(paths)))
    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {total_files} files to organize")

    if dry_run:
        console.print("[yellow]Dry run — no files were moved. Use --execute to apply.[/yellow]")
        return moves

    if not click.confirm("Organize files into subdirectories?"):
        console.print("[dim]Cancelled.[/dim]")
        return {}

    for category, paths in moves.items():
        dest_dir = result.target / category
        dest_dir.mkdir(exist_ok=True)
        for p in paths:
            dest = dest_dir / p.name
            if dest.exists():
                dest = dest_dir / f"{p.stem}_1{p.suffix}"
            try:
                shutil.move(str(p), str(dest))
            except Exception as e:
                console.print(f"[red]Failed to move {p.name}: {e}[/red]")

    console.print(f"[green]Organized {total_files} files into subdirectories.[/green]")
    return moves
