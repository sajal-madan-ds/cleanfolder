"""Tests for duplicate detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleanfolder.duplicates import (
    find_exact_duplicates,
    find_near_duplicates,
    _normalize_stem,
)
from cleanfolder.scanner import scan_folder


@pytest.fixture
def dup_folder(tmp_path: Path) -> Path:
    """Create a folder with known duplicate and near-duplicate files."""
    content_a = b"identical content here"
    (tmp_path / "original.txt").write_bytes(content_a)
    (tmp_path / "original (1).txt").write_bytes(content_a)
    (tmp_path / "original-copy.txt").write_bytes(content_a)

    (tmp_path / "report.pdf").write_bytes(b"pdf content v1")
    (tmp_path / "report (2).pdf").write_bytes(b"pdf content v2 slightly different")

    (tmp_path / "unique.png").write_bytes(b"unique image data")
    return tmp_path


def test_exact_duplicates_found(dup_folder: Path):
    files = scan_folder(dup_folder, show_progress=False)
    groups = find_exact_duplicates(files)
    assert len(groups) >= 1
    exact_group = groups[0]
    assert exact_group.kind == "exact"
    names = {f.name for f in exact_group.files}
    assert "original.txt" in names
    assert "original (1).txt" in names
    assert "original-copy.txt" in names


def test_exact_duplicates_reclaimable_space(dup_folder: Path):
    files = scan_folder(dup_folder, show_progress=False)
    groups = find_exact_duplicates(files)
    for g in groups:
        assert g.space_reclaimable > 0
        assert g.recommended_keep is not None
        assert g.recommended_keep in g.files


def test_near_duplicates_found(dup_folder: Path):
    files = scan_folder(dup_folder, show_progress=False)
    groups = find_near_duplicates(files)
    all_near_names = set()
    for g in groups:
        for f in g.files:
            all_near_names.add(f.name)
    assert "report.pdf" in all_near_names or "report (2).pdf" in all_near_names


def test_no_false_positives_for_unique(dup_folder: Path):
    files = scan_folder(dup_folder, show_progress=False)
    exact = find_exact_duplicates(files)
    for g in exact:
        names = {f.name for f in g.files}
        assert "unique.png" not in names


def test_normalize_stem():
    assert _normalize_stem("report (1).pdf") == "report"
    assert _normalize_stem("report-copy.pdf") == "report"
    assert _normalize_stem("photo 2.jpg") == "photo"
    assert _normalize_stem("document.docx") == "document"


def test_empty_folder(tmp_path: Path):
    files = scan_folder(tmp_path, show_progress=False)
    assert files == []
    assert find_exact_duplicates(files) == []
    assert find_near_duplicates(files) == []
