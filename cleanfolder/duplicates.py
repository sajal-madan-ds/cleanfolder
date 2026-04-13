"""Duplicate detection — exact hashes, fuzzy filenames, and LLM-assisted grouping."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from thefuzz import fuzz

from cleanfolder.llm.base import LLMProvider
from cleanfolder.utils import FileInfo, FolderInfo, format_size


@dataclass
class DuplicateGroup:
    """A set of files considered duplicates or near-duplicates."""

    kind: str  # "exact", "near", "llm"
    files: list[FileInfo]
    reason: str
    recommended_keep: FileInfo | None = None
    space_reclaimable: int = 0

    def __post_init__(self):
        if self.files and self.recommended_keep is None:
            self.recommended_keep = _pick_best_to_keep(self.files)
        self.space_reclaimable = sum(
            f.size for f in self.files if f is not self.recommended_keep
        )


def find_exact_duplicates(files: list[FileInfo]) -> list[DuplicateGroup]:
    """Group files with identical SHA-256 hashes (same content)."""
    size_buckets: dict[int, list[FileInfo]] = defaultdict(list)
    for f in files:
        size_buckets[f.size].append(f)

    groups: list[DuplicateGroup] = []
    for size, bucket in size_buckets.items():
        if len(bucket) < 2:
            continue
        hash_map: dict[str, list[FileInfo]] = defaultdict(list)
        for f in bucket:
            hash_map[f.hash].append(f)
        for h, dups in hash_map.items():
            if len(dups) >= 2:
                groups.append(DuplicateGroup(
                    kind="exact",
                    files=dups,
                    reason=f"Identical content (SHA-256: {h[:12]}...)",
                ))
    return groups


def find_near_duplicates(
    files: list[FileInfo],
    *,
    similarity_threshold: int = 80,
) -> list[DuplicateGroup]:
    """
    Find files with similar names that are likely duplicates.

    Catches patterns like: report.pdf / report (1).pdf / report-copy.pdf
    """
    groups: list[DuplicateGroup] = []
    used: set[Path] = set()

    stem_map: dict[str, list[FileInfo]] = defaultdict(list)
    for f in files:
        stem_map[f.extension].append(f)

    for ext, bucket in stem_map.items():
        if len(bucket) < 2:
            continue
        for i, a in enumerate(bucket):
            if a.path in used:
                continue
            cluster = [a]
            stem_a = _normalize_stem(a.name)
            for b in bucket[i + 1:]:
                if b.path in used:
                    continue
                stem_b = _normalize_stem(b.name)
                score = fuzz.ratio(stem_a, stem_b)
                if score >= similarity_threshold:
                    cluster.append(b)
            if len(cluster) >= 2:
                used.update(f.path for f in cluster)
                groups.append(DuplicateGroup(
                    kind="near",
                    files=cluster,
                    reason=f"Similar filenames (fuzzy match ≥{similarity_threshold}%)",
                ))
    return groups


async def find_llm_duplicates(
    files: list[FileInfo],
    provider: LLMProvider,
) -> list[DuplicateGroup]:
    """
    Use an LLM to identify duplicate/redundant file groups from filenames.

    Sends batches of filenames and asks the model to cluster them.
    """
    if len(files) < 2:
        return []

    file_list = "\n".join(
        f"- {f.name}  ({format_size(f.size)}, modified {f.modified:%Y-%m-%d})"
        for f in files
    )

    system = (
        "You are a file organization expert. Analyze the following list of files "
        "and identify groups that appear to be duplicates, near-duplicates, or "
        "different versions of the same file. Consider filename patterns, numbering "
        "schemes (e.g. '(1)', '-copy', '-v2'), and file sizes.\n\n"
        "Respond ONLY with valid JSON — an array of objects, each with:\n"
        '  "group_name": short description,\n'
        '  "files": [list of exact filenames],\n'
        '  "reason": why they look like duplicates\n\n'
        "If no duplicates are found, return an empty array []."
    )

    prompt = f"Here are the files in the folder:\n\n{file_list}"

    try:
        raw = await provider.complete(prompt, system=system)
        return _parse_llm_response(raw, files)
    except Exception:
        return []


def _parse_llm_response(raw: str, files: list[FileInfo]) -> list[DuplicateGroup]:
    """Parse the JSON response from the LLM into DuplicateGroups."""
    raw = raw.strip()
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        return []

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return []

    name_to_file = {f.name: f for f in files}
    groups: list[DuplicateGroup] = []

    for item in data:
        if not isinstance(item, dict):
            continue
        matched = [name_to_file[n] for n in item.get("files", []) if n in name_to_file]
        if len(matched) >= 2:
            groups.append(DuplicateGroup(
                kind="llm",
                files=matched,
                reason=item.get("reason", "LLM identified as potential duplicates"),
            ))

    return groups


# ── helpers ──────────────────────────────────────────────────────────────────

_COPY_PATTERN = re.compile(r"[\s\-_]*(copy|копия|\(\d+\)|\d+)$", re.IGNORECASE)


def _normalize_stem(filename: str) -> str:
    """Strip copy-indicators and extension to get a canonical stem for comparison."""
    stem = Path(filename).stem
    return _COPY_PATTERN.sub("", stem).strip().lower()


def _pick_best_to_keep(files: list[FileInfo]) -> FileInfo:
    """Heuristic: keep the file with the shortest name (likely the 'original')."""
    return min(files, key=lambda f: (len(f.name), -f.modified.timestamp()))


# ── folder-level duplicate detection ─────────────────────────────────────────


@dataclass
class DuplicateFolderGroup:
    """A set of subdirectories that appear to be duplicates."""

    folders: list[FolderInfo]
    reason: str
    recommended_keep: FolderInfo | None = None
    space_reclaimable: int = 0

    def __post_init__(self):
        if self.folders and self.recommended_keep is None:
            self.recommended_keep = min(
                self.folders, key=lambda f: (len(f.name), -f.modified.timestamp())
            )
        self.space_reclaimable = sum(
            f.total_size for f in self.folders if f is not self.recommended_keep
        )


def find_similar_folders(
    folders: list[FolderInfo],
    *,
    similarity_threshold: int = 80,
) -> list[DuplicateFolderGroup]:
    """Find subdirectories with similar names (e.g. 'Project' vs 'Project (1)')."""
    groups: list[DuplicateFolderGroup] = []
    used: set[Path] = set()

    for i, a in enumerate(folders):
        if a.path in used:
            continue
        cluster = [a]
        stem_a = _normalize_stem(a.name)
        for b in folders[i + 1:]:
            if b.path in used:
                continue
            stem_b = _normalize_stem(b.name)
            score = fuzz.ratio(stem_a, stem_b)
            if score >= similarity_threshold:
                cluster.append(b)
        if len(cluster) >= 2:
            used.update(f.path for f in cluster)
            groups.append(DuplicateFolderGroup(
                folders=cluster,
                reason=f"Similar folder names (fuzzy match ≥{similarity_threshold}%)",
            ))

    return groups


def find_empty_folders(folders: list[FolderInfo]) -> list[FolderInfo]:
    """Return folders that contain zero files."""
    return [f for f in folders if f.is_empty]
