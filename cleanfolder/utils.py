"""Utility functions and data models for CleanFolder."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class FileInfo:
    """Metadata about a single file discovered during scanning."""

    name: str
    path: Path
    size: int
    extension: str
    mime_type: str | None
    created: datetime
    modified: datetime
    _hash: str | None = field(default=None, repr=False)

    @property
    def hash(self) -> str:
        """Lazily compute SHA-256 hash on first access."""
        if self._hash is None:
            self._hash = compute_sha256(self.path)
        return self._hash

    def age_days(self) -> int:
        """Days since the file was last modified."""
        now = datetime.now(timezone.utc)
        modified_utc = self.modified.replace(tzinfo=timezone.utc) if self.modified.tzinfo is None else self.modified
        return (now - modified_utc).days


def compute_sha256(path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file, reading in chunks to stay memory-friendly."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def format_size(size_bytes: int) -> str:
    """Human-readable file size string."""
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    size = float(size_bytes)
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    if idx == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[idx]}"


def get_mime_type(path: Path) -> str | None:
    """Guess MIME type from file extension."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime


def file_created_time(path: Path) -> datetime:
    """Get file creation time (macOS: st_birthtime, fallback: st_ctime)."""
    stat = path.stat()
    ts = getattr(stat, "st_birthtime", stat.st_ctime)
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def file_modified_time(path: Path) -> datetime:
    """Get file modification time."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def load_config(config_path: Path | None = None) -> dict:
    """Load YAML config, falling back to defaults shipped with the package."""
    import yaml

    if config_path is None:
        candidates = [
            Path.cwd() / "config.yaml",
            Path(__file__).parent.parent / "config.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = candidate
                break

    if config_path and config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}

    return _default_config()


def _default_config() -> dict:
    return {
        "llm": {
            "default_provider": "openai",
            "fallback_order": ["openai", "anthropic", "ollama", "vllm"],
            "openai": {"model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
            "anthropic": {"model": "claude-sonnet-4-20250514", "api_key_env": "ANTHROPIC_API_KEY"},
            "ollama": {"model": "llama3", "base_url": "http://localhost:11434"},
            "vllm": {"model": "meta-llama/Llama-3-8b", "base_url": "http://localhost:8000"},
        },
        "scan": {
            "skip_hidden": True,
            "skip_patterns": [".DS_Store", "__MACOSX", "Thumbs.db", ".localized"],
            "large_file_threshold_mb": 100,
            "old_file_days": 90,
            "max_files": 10000,
        },
    }
