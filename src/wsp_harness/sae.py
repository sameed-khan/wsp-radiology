"""Validate and seed the optional, label-free SAE package."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .evidence import sha256


def validate_package(path: Path) -> str:
    """Check complete manifest coverage and contents; return manifest SHA-256."""
    if not path.is_dir():
        raise ValueError(f'SAE package missing: {path}')
    manifest_path = path / 'manifest.json'
    try:
        manifest = json.loads(manifest_path.read_text())
        if not isinstance(manifest, dict) or not manifest:
            raise ValueError('empty or invalid manifest')
        actual = set()
        for p in path.rglob('*'):
            if p.is_symlink() or not (p.is_file() or p.is_dir()):
                raise ValueError('SAE package contains a symlink or special file')
            if p.is_file() and p != manifest_path:
                actual.add(p.relative_to(path).as_posix())
        if actual != set(manifest):
            raise ValueError('SAE manifest coverage mismatch')
        for name, value in manifest.items():
            if 'test' in name.lower() or not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
                raise ValueError('invalid SAE manifest entry')
            if sha256(path / name) != value:
                raise ValueError(f'SAE hash mismatch: {name}')
        return sha256(manifest_path)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f'invalid SAE package: {path}') from exc


def seed_package(source: Path, destination: Path) -> str:
    expected = validate_package(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    if validate_package(destination) != expected:
        raise ValueError('SAE package changed during copy')
    for p in destination.rglob('*'):
        p.chmod(0o555 if p.is_dir() else 0o444)
    destination.chmod(0o555)
    return expected
