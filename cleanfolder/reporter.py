"""Report generator — rich terminal output and optional markdown export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cleanfolder.analyzer import AnalysisResult
from cleanfolder.duplicates import DuplicateGroup
from cleanfolder.utils import format_size

console = Console()


def print_report(result: AnalysisResult) -> None:
    """Print a full analysis report to the terminal."""
    _print_header(result)
    _print_category_breakdown(result)
    _print_duplicates(result)
    _print_large_files(result)
    _print_old_files(result)
    _print_temp_files(result)
    _print_llm_suggestions(result)
    _print_summary(result)


def export_markdown(result: AnalysisResult, output_path: Path) -> None:
    """Export the analysis report as a markdown file."""
    lines: list[str] = []
    lines.append(f"# Folder Analysis Report")
    lines.append(f"**Target:** `{result.target}`  ")
    lines.append(f"**Date:** {datetime.now():%Y-%m-%d %H:%M}  ")
    lines.append(f"**Files scanned:** {len(result.files)}  ")
    lines.append(f"**Total size:** {format_size(result.total_size)}  ")
    lines.append("")

    # Categories
    lines.append("## File Categories")
    lines.append("| Category | Files | Size |")
    lines.append("|----------|------:|-----:|")
    for cat, files in sorted(result.categories.by_category.items()):
        total = sum(f.size for f in files)
        lines.append(f"| {cat} | {len(files)} | {format_size(total)} |")
    lines.append("")

    # Duplicates
    all_dups = result.all_duplicates
    if all_dups:
        lines.append("## Duplicates Found")
        lines.append(f"**Groups:** {len(all_dups)}  ")
        lines.append(f"**Reclaimable space:** {format_size(result.reclaimable_size)}  ")
        lines.append("")
        for i, group in enumerate(all_dups, 1):
            lines.append(f"### Group {i} ({group.kind})")
            lines.append(f"*{group.reason}*")
            lines.append("")
            for f in group.files:
                keep = " **(keep)**" if f is group.recommended_keep else ""
                lines.append(f"- `{f.name}` ({format_size(f.size)}){keep}")
            lines.append("")

    # Large files
    if result.categories.large_files:
        lines.append("## Large Files")
        for f in sorted(result.categories.large_files, key=lambda x: -x.size):
            lines.append(f"- `{f.name}` — {format_size(f.size)}")
        lines.append("")

    # Temp files
    if result.categories.temp_files:
        lines.append("## Temporary Files")
        for f in result.categories.temp_files:
            lines.append(f"- `{f.name}` ({format_size(f.size)})")
        lines.append("")

    # LLM suggestions
    if result.llm_suggestions:
        lines.append("## AI Suggestions")
        lines.append(result.llm_suggestions)
        lines.append("")

    output_path.write_text("\n".join(lines))
    console.print(f"[green]Report exported to {output_path}[/green]")


# ── internal helpers ─────────────────────────────────────────────────────────


def _print_header(result: AnalysisResult) -> None:
    header = Text()
    header.append("CleanFolder Analysis\n", style="bold magenta")
    header.append(f"Target: {result.target}\n", style="dim")
    header.append(f"Files:  {len(result.files)}   Size: {format_size(result.total_size)}")
    console.print(Panel(header, border_style="blue"))
    console.print()


def _print_category_breakdown(result: AnalysisResult) -> None:
    if not result.categories.by_category:
        return

    table = Table(title="File Categories", show_lines=False, padding=(0, 2))
    table.add_column("Category", style="bold")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right", style="cyan")
    table.add_column("% of Total", justify="right", style="dim")

    total = result.total_size or 1
    for cat, files in sorted(
        result.categories.by_category.items(),
        key=lambda x: -sum(f.size for f in x[1]),
    ):
        cat_size = sum(f.size for f in files)
        pct = cat_size / total * 100
        table.add_row(cat, str(len(files)), format_size(cat_size), f"{pct:.1f}%")

    console.print(table)
    console.print()


def _print_duplicates(result: AnalysisResult) -> None:
    all_dups = result.all_duplicates
    if not all_dups:
        console.print("[green]No duplicates found.[/green]\n")
        return

    console.print(
        f"[bold red]Found {len(all_dups)} duplicate groups "
        f"({format_size(result.reclaimable_size)} reclaimable)[/bold red]\n"
    )

    for i, group in enumerate(all_dups, 1):
        table = Table(
            title=f"Group {i} — {group.kind.upper()} duplicate",
            caption=group.reason,
            show_lines=True,
        )
        table.add_column("File", style="white")
        table.add_column("Size", justify="right")
        table.add_column("Modified", style="dim")
        table.add_column("Action", justify="center")

        for f in group.files:
            is_keep = f is group.recommended_keep
            action = "[green]KEEP[/green]" if is_keep else "[red]REMOVE[/red]"
            style = "bold" if is_keep else ""
            table.add_row(
                Text(f.name, style=style),
                format_size(f.size),
                f"{f.modified:%Y-%m-%d}",
                action,
            )

        console.print(table)
        console.print()


def _print_large_files(result: AnalysisResult) -> None:
    large = result.categories.large_files
    if not large:
        return

    table = Table(title="Large Files", show_lines=False)
    table.add_column("File", style="yellow")
    table.add_column("Size", justify="right", style="bold red")
    table.add_column("Modified", style="dim")

    for f in sorted(large, key=lambda x: -x.size)[:15]:
        table.add_row(f.name, format_size(f.size), f"{f.modified:%Y-%m-%d}")

    console.print(table)
    console.print()


def _print_old_files(result: AnalysisResult) -> None:
    old = result.categories.old_files
    if not old:
        return

    total_size = sum(f.size for f in old)
    console.print(
        f"[yellow]Old files (not modified recently):[/yellow] "
        f"{len(old)} files ({format_size(total_size)})\n"
    )


def _print_temp_files(result: AnalysisResult) -> None:
    temp = result.categories.temp_files
    if not temp:
        return

    total_size = sum(f.size for f in temp)
    table = Table(title="Temporary / Incomplete Files", show_lines=False)
    table.add_column("File", style="red")
    table.add_column("Size", justify="right")

    for f in temp:
        table.add_row(f.name, format_size(f.size))

    console.print(table)
    console.print(f"[bold]Total temp file size:[/bold] {format_size(total_size)}\n")


def _print_llm_suggestions(result: AnalysisResult) -> None:
    if not result.llm_suggestions:
        return

    console.print(Panel(
        result.llm_suggestions,
        title="AI Cleanup Suggestions",
        border_style="green",
    ))
    console.print()


def _print_summary(result: AnalysisResult) -> None:
    reclaimable = result.reclaimable_size + result.temp_reclaimable
    summary = Table(title="Summary", show_header=False, show_lines=False, padding=(0, 2))
    summary.add_column("Label", style="bold")
    summary.add_column("Value", style="cyan")

    summary.add_row("Total files", str(len(result.files)))
    summary.add_row("Total size", format_size(result.total_size))
    summary.add_row("Duplicate groups", str(len(result.all_duplicates)))
    summary.add_row("Temp files", str(len(result.categories.temp_files)))
    summary.add_row("Estimated reclaimable", format_size(reclaimable))

    console.print(summary)
    console.print()
