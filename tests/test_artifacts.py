import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location("archive_artifacts", Path(__file__).parents[1] / "scripts/archive_artifacts.py")
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "ROOT", tmp_path)
    (tmp_path / "artifact-staging").mkdir()
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifact-staging/report.txt").write_text("reviewed report\n")
    return tmp_path


def args(*extra):
    return ["--archive", "run.tar", "--reviewed", "--file", "reports:report.txt:run-1", *extra]


def test_inspection_and_deterministic_archive(repo, capsys):
    assert a.main(args()) == 0
    assert not list((repo / "artifacts").iterdir())
    assert a.main(args("--write")) == 0
    archive = repo / "artifacts/run.tar"
    first = archive.read_bytes()
    assert archive.stat().st_mode & 0o777 == 0o600
    with tarfile.open(fileobj=io.BytesIO(first)) as tar:
        assert tar.getnames() == ["manifest.json", "files/report.txt"]
        manifest = json.load(tar.extractfile("manifest.json"))
        assert manifest["files"][0]["sha256"] == hashlib.sha256(b"reviewed report\n").hexdigest()
        assert manifest["files"][0]["generated_origin"] == "run-1"
    assert hashlib.sha256(first).hexdigest() in capsys.readouterr().out
    assert a.main(args("--write")) == 1
    assert archive.read_bytes() == first
    assert a.main(args("--write", "--overwrite")) == 0
    assert archive.read_bytes() == first


def test_requires_review_and_explicit_flags(repo):
    assert a.main(["--archive", "run.tar", "--file", "reports:report.txt:run-1"]) == 1
    assert a.main(args("--dvc-add")) == 1
    assert a.main(args("--write", "--push")) == 1
    assert not list((repo / "artifacts").iterdir())


@pytest.mark.parametrize("path", ["../report.txt", "/etc/passwd", "secret.txt", ".env", "data/x", "photo.jpg", "session/log.txt"])
def test_bad_paths_refused(repo, path):
    assert a.main(["--archive", "run.tar", "--reviewed", "--write", "--file", f"logs:{path}:run-1"]) == 1
    assert not list((repo / "artifacts").iterdir())


def test_symlinks_special_files_and_output_escape(repo):
    stage = repo / "artifact-staging"
    (stage / "link.txt").symlink_to(stage / "report.txt")
    (stage / "nested").symlink_to(stage, target_is_directory=True)
    os.mkfifo(stage / "pipe")
    for path in ("link.txt", "nested/report.txt", "pipe"):
        assert a.main(["--archive", "run.tar", "--reviewed", "--write", "--file", f"logs:{path}:run-1"]) == 1
    assert a.main(["--archive", "../escape.tar", "--reviewed", "--file", "reports:report.txt:run-1", "--write"]) == 1
    (repo / "artifacts").rmdir()
    (repo / "artifacts").symlink_to(stage, target_is_directory=True)
    assert a.main(args("--write")) == 1
    assert not (stage / "run.tar").exists()


def test_secret_and_bounds_fail_before_install(repo, monkeypatch, capsys):
    (repo / "artifact-staging/bad.txt").write_text("password = supersecretvalue")
    assert a.main(args("--write", "--file", "logs:bad.txt:run-1")) == 1
    assert "supersecretvalue" not in capsys.readouterr().err
    assert not list((repo / "artifacts").iterdir())
    monkeypatch.setattr(a, "MAX_BYTES", 2)
    assert a.main(args("--write")) == 1
    assert not list((repo / "artifacts").iterdir())


def test_dvc_explicit_and_suppressed_failure(repo, monkeypatch, capsys):
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(a.subprocess, "run", run)
    assert a.main(args("--write", "--dvc-add", "--push")) == 0
    assert [call.args[0] for call in run.call_args_list] == [
        ["dvc", "add", "--", "artifacts/run.tar"],
        ["dvc", "push", "-r", "b2", "--", "artifacts/run.tar.dvc"],
    ]
    assert all(call.kwargs.get("shell") is not True for call in run.call_args_list)
    run.return_value = Mock(returncode=1, stderr=b"secret output")
    assert a.main(args("--write", "--overwrite", "--dvc-add")) == 1
    assert "secret output" not in capsys.readouterr().err
