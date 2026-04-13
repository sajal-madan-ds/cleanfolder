"""Analyzer — orchestrates scanning, duplicate detection, and categorization."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cleanfolder.categorizer import CategoryResult, categorize_files, get_llm_suggestions
from cleanfolder.duplicates import (
    DuplicateGroup,
    find_exact_duplicates,
    find_llm_duplicates,
    find_near_duplicates,
)
from cleanfolder.llm.base import LLMProvider
from cleanfolder.scanner import scan_folder
from cleanfolder.utils import FileInfo


@dataclass
class AnalysisResult:
    """Complete analysis of a folder."""

    target: Path
    files: list[FileInfo]
    exact_duplicates: list[DuplicateGroup] = field(default_factory=list)
    near_duplicates: list[DuplicateGroup] = field(default_factory=list)
    llm_duplicates: list[DuplicateGroup] = field(default_factory=list)
    categories: CategoryResult = field(default_factory=CategoryResult)
    llm_suggestions: str = ""

    @property
    def all_duplicates(self) -> list[DuplicateGroup]:
        return self.exact_duplicates + self.near_duplicates + self.llm_duplicates

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)

    @property
    def reclaimable_size(self) -> int:
        return sum(g.space_reclaimable for g in self.all_duplicates)

    @property
    def temp_reclaimable(self) -> int:
        return sum(f.size for f in self.categories.temp_files)


async def analyze_folder(
    target: Path,
    provider: LLMProvider | None = None,
    *,
    scan_config: dict | None = None,
    duplicates_only: bool = False,
    show_progress: bool = True,
) -> AnalysisResult:
    """
    Run the full analysis pipeline on a folder.

    1. Scan the folder for files
    2. Find exact duplicates (hash-based)
    3. Find near duplicates (fuzzy filename matching)
    4. Optionally use LLM for deeper duplicate detection
    5. Categorize files and get LLM suggestions
    """
    cfg = scan_config or {}

    files = scan_folder(
        target,
        skip_hidden=cfg.get("skip_hidden", True),
        skip_patterns=cfg.get("skip_patterns"),
        max_files=cfg.get("max_files", 10_000),
        show_progress=show_progress,
    )

    result = AnalysisResult(target=target, files=files)

    result.exact_duplicates = find_exact_duplicates(files)
    result.near_duplicates = find_near_duplicates(files)

    if provider:
        result.llm_duplicates = await find_llm_duplicates(files, provider)

    if not duplicates_only:
        result.categories = categorize_files(
            files,
            large_threshold_mb=cfg.get("large_file_threshold_mb", 100),
            old_days=cfg.get("old_file_days", 90),
        )
        if provider:
            result.llm_suggestions = await get_llm_suggestions(result.categories, provider)

    return result
