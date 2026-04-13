"""Tests for the folder scanner."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleanfolder.scanner import scan_folder, scan_subfolders
from cleanfolder.utils import FileInfo


@pytest.fixture
def sample_folder(tmp_path: Path) -> Path:
    """Create a temporary folder with sample files for testing."""
    (tmp_path / "hello.txt").write_text("Hello, world!")
    (tmp_path / "data.csv").write_text("a,b,c\n1,2,3\n")
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.py").write_text("print('nested')")
    (tmp_path / ".hidden_file").write_text("secret")
    (tmp_path / ".DS_Store").write_bytes(b"\x00" * 10)
    return tmp_path


def test_scan_finds_all_visible_files(sample_folder: Path):
    files = scan_folder(sample_folder, show_progress=False)
    names = {f.name for f in files}
    assert "hello.txt" in names
    assert "data.csv" in names
    assert "photo.jpg" in names
    assert "nested.py" in names


def test_scan_skips_hidden_files(sample_folder: Path):
    files = scan_folder(sample_folder, show_progress=False, skip_hidden=True)
    names = {f.name for f in files}
    assert ".hidden_file" not in names
    assert ".DS_Store" not in names


def test_scan_includes_hidden_when_requested(sample_folder: Path):
    files = scan_folder(sample_folder, show_progress=False, skip_hidden=False)
    names = {f.name for f in files}
    assert ".hidden_file" in names


def test_scan_skips_ds_store_even_when_not_hidden(sample_folder: Path):
    files = scan_folder(
        sample_folder,
        show_progress=False,
        skip_hidden=False,
        skip_patterns=[".DS_Store"],
    )
    names = {f.name for f in files}
    assert ".DS_Store" not in names


def test_scan_returns_file_info_fields(sample_folder: Path):
    files = scan_folder(sample_folder, show_progress=False)
    txt = next(f for f in files if f.name == "hello.txt")
    assert txt.extension == ".txt"
    assert txt.size == len("Hello, world!")
    assert txt.mime_type == "text/plain"
    assert txt.path.exists()


def test_scan_max_files_raises(sample_folder: Path):
    with pytest.raises(RuntimeError, match="limit"):
        scan_folder(sample_folder, show_progress=False, max_files=1)


def test_scan_not_a_directory(tmp_path: Path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(NotADirectoryError):
        scan_folder(f, show_progress=False)


def test_file_info_lazy_hash(sample_folder: Path):
    files = scan_folder(sample_folder, show_progress=False)
    txt = next(f for f in files if f.name == "hello.txt")
    assert txt._hash is None
    h = txt.hash
    assert isinstance(h, str) and len(h) == 64
    assert txt._hash == h


def test_scan_subfolders(sample_folder: Path):
    folders = scan_subfolders(sample_folder)
    names = {f.name for f in folders}
    assert "subdir" in names


def test_scan_subfolders_detects_empty(tmp_path: Path):
    (tmp_path / "empty_dir").mkdir()
    (tmp_path / "has_files").mkdir()
    (tmp_path / "has_files" / "a.txt").write_text("content")
    folders = scan_subfolders(tmp_path)
    empty = [f for f in folders if f.is_empty]
    non_empty = [f for f in folders if not f.is_empty]
    assert any(f.name == "empty_dir" for f in empty)
    assert any(f.name == "has_files" for f in non_empty)


def test_scan_subfolders_counts_files(tmp_path: Path):
    d = tmp_path / "mydir"
    d.mkdir()
    (d / "a.txt").write_text("aaa")
    (d / "b.txt").write_text("bbb")
    folders = scan_subfolders(tmp_path)
    mydir = next(f for f in folders if f.name == "mydir")
    assert mydir.file_count == 2
    assert mydir.total_size > 0
