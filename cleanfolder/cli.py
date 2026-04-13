"""CLI entry point for CleanFolder — built with Click."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from cleanfolder.utils import load_config

console = Console()


@click.group()
@click.version_option(package_name="cleanfolder")
def main():
    """CleanFolder — LLM-powered folder cleaning agent for macOS."""
    load_dotenv()


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "ollama", "vllm"]), default=None, help="LLM provider to use (auto-detects if omitted).")
@click.option("--dry-run/--execute", default=True, help="Preview changes (default) or execute them.")
@click.option("--duplicates-only", is_flag=True, help="Only scan for duplicates, skip categorization.")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False), default=None, help="Path to config.yaml.")
@click.option("--export", "export_path", type=click.Path(dir_okay=False), default=None, help="Export report to a markdown file.")
@click.option("--max-files", type=int, default=None, help="Override max file limit.")
@click.option("--no-llm", is_flag=True, help="Skip all LLM calls (offline mode).")
@click.option("--action", type=click.Choice(["report", "trash-duplicates", "trash-temp", "organize", "archive"]), default="report", help="Action to perform after analysis.")
def scan(
    folder: str,
    provider: str | None,
    dry_run: bool,
    duplicates_only: bool,
    config_path: str | None,
    export_path: str | None,
    max_files: int | None,
    no_llm: bool,
    action: str,
):
    """Scan a folder and analyze its contents."""
    asyncio.run(_scan_async(
        folder=Path(folder),
        provider_name=provider,
        dry_run=dry_run,
        duplicates_only=duplicates_only,
        config_path=Path(config_path) if config_path else None,
        export_path=Path(export_path) if export_path else None,
        max_files=max_files,
        no_llm=no_llm,
        action=action,
    ))


async def _scan_async(
    folder: Path,
    provider_name: str | None,
    dry_run: bool,
    duplicates_only: bool,
    config_path: Path | None,
    export_path: Path | None,
    max_files: int | None,
    no_llm: bool,
    action: str,
):
    from cleanfolder.analyzer import analyze_folder
    from cleanfolder.reporter import print_report, export_markdown

    cfg = load_config(config_path)
    scan_cfg = cfg.get("scan", {})
    if max_files is not None:
        scan_cfg["max_files"] = max_files

    llm_provider = None
    if not no_llm:
        try:
            from cleanfolder.llm.router import get_provider
            llm_provider = await get_provider(cfg, preferred=provider_name)
            console.print(f"[dim]Using LLM provider: {llm_provider.name}[/dim]\n")
        except RuntimeError as e:
            console.print(f"[yellow]LLM unavailable: {e}[/yellow]")
            console.print("[dim]Continuing without LLM assistance...[/dim]\n")

    result = await analyze_folder(
        folder,
        provider=llm_provider,
        scan_config=scan_cfg,
        duplicates_only=duplicates_only,
    )

    print_report(result)

    if export_path:
        export_markdown(result, export_path)

    if action != "report":
        _execute_action(action, result, dry_run=dry_run)


def _execute_action(action: str, result, *, dry_run: bool):
    from cleanfolder.actions import (
        trash_duplicates,
        trash_temp_files,
        organize_files,
        archive_files,
    )

    if action == "trash-duplicates":
        trash_duplicates(result.all_duplicates, dry_run=dry_run)
    elif action == "trash-temp":
        trash_temp_files(result.categories.temp_files, dry_run=dry_run)
    elif action == "organize":
        organize_files(result, dry_run=dry_run)
    elif action == "archive":
        from datetime import datetime
        archive_path = result.target / f"archive_{datetime.now():%Y%m%d_%H%M%S}.zip"
        old_files = result.categories.old_files
        if old_files:
            archive_files(old_files, archive_path, dry_run=dry_run)
        else:
            console.print("[dim]No old files to archive.[/dim]")


@main.command()
def config():
    """Show current configuration."""
    cfg = load_config()
    from rich.syntax import Syntax
    import yaml

    console.print(Panel(
        Syntax(yaml.dump(cfg, default_flow_style=False), "yaml", theme="monokai"),
        title="Current Configuration",
        border_style="blue",
    ))


# Allow `python -m cleanfolder` to work
if __name__ == "__main__":
    main()
