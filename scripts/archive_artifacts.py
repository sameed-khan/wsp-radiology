#!/usr/bin/env python3
"""Package explicitly selected, human-reviewed generated artifacts; never discover files."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MAX_FILES = 100
MAX_BYTES = 128 * 1024 * 1024
CATEGORIES = {"reports", "logs", "transcripts", "mappings", "checkpoints"}
SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
FORBIDDEN_NAME = re.compile(
    r"(?i)(?:^|[._-])(credential|credentials|secret|secrets|token|tokens|password|passwd|"
    r"private|session|sessions|runtime|dataset|datasets|features|weights|model|models|"
    r"data|rclone|huggingface|kaggle|aws|b2|env)(?:$|[._-])"
)
SECRET_CONTENT = re.compile(
    rb"(?i)(?:-----BEGIN (?:[A-Z ]* )?PRIVATE KEY-----|"
    rb"\b(?:hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b|"
    rb"\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|password|passwd|"
    rb"authorization|b2_application_key)\s*[\"']?\s*[:=]\s*[\"']?[^\s\"',;]{4,})"
)


class Refusal(Exception):
    pass


def safe_parts(value, *, output=False):
    parts = value.split("/")
    if not output and parts[-1].lower().endswith((".zip", ".gz", ".tgz", ".tar", ".7z", ".rar", ".jpg", ".jpeg", ".png", ".dcm", ".parquet")):
        raise Refusal("Archive, image, and dataset-like file formats are prohibited.")
    if not parts or any(not SAFE_COMPONENT.fullmatch(p) or p in {".", ".."}
                        or FORBIDDEN_NAME.search(p) for p in parts):
        raise Refusal("Unsafe or prohibited path/name; select a safely named curated file.")
    return parts


def open_directory(parent_fd, name):
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)


def read_staged(root_fd, path, remaining):
    parts = safe_parts(path)
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = open_directory(fd, part)
            os.close(fd)
            fd = child
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            info = os.fstat(file_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > remaining:
                raise Refusal("Input is not a regular file or exceeds the archive size limit.")
            with os.fdopen(file_fd, "rb", closefd=False) as stream:
                data = stream.read(remaining + 1)
            if len(data) > remaining or len(data) != info.st_size:
                raise Refusal("Input changed during reading or exceeds the archive size limit.")
            if SECRET_CONTENT.search(data):
                raise Refusal("Potential credential pattern detected; remove it and review the staged content again.")
            return data
        finally:
            os.close(file_fd)
    finally:
        os.close(fd)


def parse_selection(value):
    parts = value.split(":", 2)
    if len(parts) != 3 or parts[0] not in CATEGORIES:
        raise Refusal("Selection must be CATEGORY:RELATIVE_PATH:GENERATED_ORIGIN.")
    category, path, origin = parts
    safe_parts(path)
    # Origin is a short, non-secret identifier, not a URL or free-form command.
    if not SAFE_COMPONENT.fullmatch(origin) or FORBIDDEN_NAME.search(origin):
        raise Refusal("Origin must be a safe generated-origin identifier without secret-like names.")
    return category, path, origin


def package(args):
    if not args.reviewed:
        raise Refusal("Explicit --reviewed acknowledgment is required, even for inspection.")
    if args.push and not args.dvc_add or args.dvc_add and not args.write:
        raise Refusal("--push requires --dvc-add, and --dvc-add requires --write.")
    if not 1 <= len(args.file) <= MAX_FILES:
        raise Refusal(f"Select between 1 and {MAX_FILES} files explicitly.")
    if len(safe_parts(args.archive, output=True)) != 1 or not args.archive.endswith(".tar"):
        raise Refusal("Archive must be a simple .tar filename under artifacts/.")
    selections = [parse_selection(s) for s in args.file]
    if len({p for _, p, _ in selections}) != len(selections):
        raise Refusal("Duplicate staged file selection.")
    selections.sort(key=lambda item: item[1])
    root_fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    staging_fd = artifacts_fd = None
    try:
        staging_fd = open_directory(root_fd, "artifact-staging")
        artifacts_fd = open_directory(root_fd, "artifacts")
        entries, total = [], 0
        for category, path, origin in selections:
            data = read_staged(staging_fd, path, MAX_BYTES - total)
            total += len(data)
            entries.append(({"path": path, "category": category, "generated_origin": origin,
                             "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}, data))
        manifest = {"format": 1, "files": [entry for entry, _ in entries]}
        print(json.dumps(manifest, indent=2, sort_keys=True))
        if not args.write:
            print("Inspection only; no archive or DVC operation performed.")
            return
        # Temporary file is private and in the destination filesystem for atomic installation.
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=".artifact-", dir=ROOT / "artifacts")
        try:
            with os.fdopen(tmp_fd, "wb") as stream:
                with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode() + b"\n"
                    add_bytes(tar, "manifest.json", payload)
                    for entry, data in entries:
                        add_bytes(tar, "files/" + entry["path"], data)
                stream.flush()
                os.fsync(stream.fileno())
            with open(tmp_path, "rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            tmp_name = os.path.basename(tmp_path)
            if args.overwrite:
                os.replace(tmp_name, args.archive, src_dir_fd=artifacts_fd, dst_dir_fd=artifacts_fd)
            else:
                os.link(tmp_name, args.archive, src_dir_fd=artifacts_fd, dst_dir_fd=artifacts_fd,
                        follow_symlinks=False)
                os.unlink(tmp_name, dir_fd=artifacts_fd)
            print(f"Archive SHA256: {digest}  artifacts/{args.archive}")
        finally:
            try:
                os.unlink(os.path.basename(tmp_path), dir_fd=artifacts_fd)
            except FileNotFoundError:
                pass
        if args.dvc_add:
            run_dvc(["dvc", "add", "--", f"artifacts/{args.archive}"])
        if args.push:
            run_dvc(["dvc", "push", "-r", "b2", "--", f"artifacts/{args.archive}.dvc"])
    finally:
        for fd in (artifacts_fd, staging_fd, root_fd):
            if fd is not None:
                os.close(fd)


def add_bytes(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o600
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    tar.addfile(info, io.BytesIO(data))


def run_dvc(argv):
    result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise Refusal("DVC operation failed; inspect DVC configuration privately before retrying.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="destination .tar filename under artifacts/")
    parser.add_argument("--file", action="append", default=[], metavar="CATEGORY:PATH:ORIGIN")
    parser.add_argument("--reviewed", action="store_true", help="acknowledge manual review of every selected file")
    parser.add_argument("--write", action="store_true", help="install archive (default is inspection only)")
    parser.add_argument("--overwrite", action="store_true", help="explicitly replace existing archive")
    parser.add_argument("--dvc-add", action="store_true")
    parser.add_argument("--push", action="store_true", help="push selected pointer to existing b2 remote")
    args = parser.parse_args(argv)
    try:
        package(args)
    except (Refusal, OSError, tarfile.TarError, ValueError):
        exc = sys.exc_info()[1]
        print(f"Refused: {exc}" if isinstance(exc, Refusal) else
              "Refused: filesystem or archive operation failed; check paths, file types and permissions privately.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
