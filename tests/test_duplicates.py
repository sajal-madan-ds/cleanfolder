"""Tests for duplicate detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleanfolder.duplicates import (
    find_exact_duplicates,
    find_near_duplicates,
    find_similar_folders,
    find_empty_folders,
    _normalize_stem,
)
from cleanfolder.scanner import scan_folder, scan_subfolders


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


def test_similar_folders_detected(tmp_path: Path):
    (tmp_path / "Project").mkdir()
    (tmp_path / "Project (1)").mkdir()
    (tmp_path / "Project-copy").mkdir()
    (tmp_path / "Unrelated").mkdir()
    folders = scan_subfolders(tmp_path)
    groups = find_similar_folders(folders)
    assert len(groups) >= 1
    group_names = {f.name for f in groups[0].folders}
    assert "Project" in group_names


def test_empty_folders_detected(tmp_path: Path):
    (tmp_path / "empty1").mkdir()
    (tmp_path / "empty2").mkdir()
    (tmp_path / "has_stuff").mkdir()
    (tmp_path / "has_stuff" / "file.txt").write_text("data")
    folders = scan_subfolders(tmp_path)
    empties = find_empty_folders(folders)
    empty_names = {f.name for f in empties}
    assert "empty1" in empty_names
    assert "empty2" in empty_names
    assert "has_stuff" not in empty_names
