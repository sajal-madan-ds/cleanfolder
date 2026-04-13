"""File categorizer — classify files by type, flag large/old/temp files, LLM suggestions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from cleanfolder.llm.base import LLMProvider
from cleanfolder.utils import FileInfo, format_size


CATEGORY_MAP: dict[str, list[str]] = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".tiff", ".ico", ".raw"],
    "Videos": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"],
    "Documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt", ".csv", ".pages", ".numbers", ".key"],
    "Archives": [".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz", ".tar.gz", ".tgz"],
    "Installers": [".dmg", ".pkg", ".app", ".exe", ".msi", ".deb", ".rpm"],
    "Code": [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".go", ".rs", ".rb", ".sh", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".xml", ".sql", ".swift", ".kt"],
    "Data": [".db", ".sqlite", ".sqlite3", ".parquet", ".arrow", ".feather", ".hdf5", ".h5"],
    "Fonts": [".ttf", ".otf", ".woff", ".woff2"],
    "Ebooks": [".epub", ".mobi", ".azw3"],
}

TEMP_PATTERNS: list[str] = [
    "*.tmp", "*.temp", "*.bak", "*.swp", "*.swo", "~*",
    "*.crdownload", "*.part", "*.download",
]


@dataclass
class CategoryResult:
    """Categorization results for a scanned folder."""

    by_category: dict[str, list[FileInfo]] = field(default_factory=dict)
    large_files: list[FileInfo] = field(default_factory=list)
    old_files: list[FileInfo] = field(default_factory=list)
    temp_files: list[FileInfo] = field(default_factory=list)
    llm_suggestions: str = ""


def categorize_files(
    files: list[FileInfo],
    *,
    large_threshold_mb: int = 100,
    old_days: int = 90,
) -> CategoryResult:
    """Categorize files by extension, flag large/old/temp files."""
    result = CategoryResult()

    ext_to_cat = {}
    for cat, exts in CATEGORY_MAP.items():
        for ext in exts:
            ext_to_cat[ext] = cat

    for f in files:
        cat = ext_to_cat.get(f.extension, "Other")
        result.by_category.setdefault(cat, []).append(f)

        if f.size > large_threshold_mb * 1024 * 1024:
            result.large_files.append(f)

        if f.age_days() > old_days:
            result.old_files.append(f)

        if _is_temp_file(f):
            result.temp_files.append(f)

    return result


async def get_llm_suggestions(
    result: CategoryResult,
    provider: LLMProvider,
) -> str:
    """Ask the LLM for cleanup and organization suggestions based on the categorization."""
    summary_lines = []
    for cat, cat_files in sorted(result.by_category.items()):
        total_size = sum(f.size for f in cat_files)
        summary_lines.append(f"- {cat}: {len(cat_files)} files ({format_size(total_size)})")

    if result.large_files:
        summary_lines.append(f"\nLarge files (>threshold): {len(result.large_files)}")
        for f in sorted(result.large_files, key=lambda x: -x.size)[:10]:
            summary_lines.append(f"  - {f.name} ({format_size(f.size)})")

    if result.old_files:
        summary_lines.append(f"\nOld files (not modified recently): {len(result.old_files)}")

    if result.temp_files:
        summary_lines.append(f"\nTemporary/incomplete files: {len(result.temp_files)}")
        for f in result.temp_files[:10]:
            summary_lines.append(f"  - {f.name}")

    summary = "\n".join(summary_lines)

    system = (
        "You are a storage optimization expert for macOS. Given a folder analysis summary, "
        "provide concise, actionable cleanup recommendations. Focus on:\n"
        "1. Which categories have the most reclaimable space\n"
        "2. Whether old/temp files should be removed\n"
        "3. Suggestions for organizing files into subdirectories\n"
        "4. Any patterns that suggest clutter (e.g. many installers)\n\n"
        "Be brief and practical. Use bullet points."
    )

    prompt = f"Here is the folder analysis:\n\n{summary}"

    try:
        return await provider.complete(prompt, system=system)
    except Exception as e:
        return f"(LLM suggestions unavailable: {e})"


def _is_temp_file(f: FileInfo) -> bool:
    """Check if a file matches known temporary/incomplete file patterns."""
    name = f.name.lower()
    if name.startswith("~"):
        return True
    temp_exts = {".tmp", ".temp", ".bak", ".swp", ".swo", ".crdownload", ".part", ".download"}
    return f.extension in temp_exts
