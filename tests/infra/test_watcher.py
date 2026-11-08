"""Watcher unit tests (no Docker): synthetic corpus, stop/alert/pool-derivative classification."""
import base64
import hashlib
import io
import json
import os
import random
import signal
import subprocess
import sys
import time
import zipfile

import imagehash
import pytest
from PIL import Image, ImageDraw

from infra import watcher as W
from infra.proxy import wsp_content as wc


def make_image(seed, size=(256, 192)):
    rnd = random.Random(seed)
    im = Image.new("L", size, rnd.randrange(40, 200))
    d = ImageDraw.Draw(im)
    for _ in range(25):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        d.ellipse([x, y, x + rnd.randrange(10, 90), y + rnd.randrange(10, 90)], fill=rnd.randrange(256))
    return im.convert("RGB")


def enc(im, fmt="JPEG", **kw):
    b = io.BytesIO()
    im.save(b, format=fmt, **kw)
    return b.getvalue()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def ph(im):
    return str(imagehash.phash(im))


TEST_IM, POOL_IM, OTHER_IM = make_image(1), make_image(2), make_image(77)
TEST_JPG, POOL_JPG = enc(TEST_IM, quality=92), enc(POOL_IM, quality=92)
NAMES = [f"{300000 + i}-{i % 3 + 1}.jpg" for i in range(8)]
ARCHIVE_SHA = "c" * 64


@pytest.fixture(scope="module")
def corpus_dict():
    return {"archive_sha256": ARCHIVE_SHA, "raw_sha256": [sha(TEST_JPG), sha(POOL_JPG)],
            "normalized_sha256": [], "phash": {"pool": [ph(POOL_IM)], "test": [ph(TEST_IM)]},
            "basenames": NAMES}


@pytest.fixture
def watch(tmp_path, corpus_dict):
    ws, ctl, st = tmp_path / "ws", tmp_path / "ctl", tmp_path / "state"
    ws.mkdir()
    return W.Watcher(ws, wc.Corpus(corpus_dict), st, ctl, "r1")


def put(w, name, data):
    p = w.workspace / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def levels(findings):
    return {f["file"]: (f["level"], f["rule"]) for f in findings}


def test_clean_workspace_has_no_findings(watch):
    put(watch, "a.jpg", enc(OTHER_IM))
    put(watch, "notes.txt", b"nothing to see here")
    assert watch.scan_once() == []
    assert not (watch.control_dir / W.STOP_FILE).exists()


def test_exact_test_image_stops_and_writes_stop_request(watch):
    put(watch, "sub/x.jpg", TEST_JPG)
    f = watch.scan_once()
    assert levels(f) == {"sub/x.jpg": ("stop", "sha256")}
    req = json.loads((watch.control_dir / W.STOP_FILE).read_text())
    assert set(req) == {"reason", "file", "rule", "time"}
    assert req["file"] == "sub/x.jpg" and req["rule"] == "sha256"
    assert (watch.control_dir / W.STOP_FILE).stat().st_mode & 0o077 == 0


def test_reencoded_and_resized_test_image_alerts(watch):
    put(watch, "a.png", enc(TEST_IM, "PNG"))
    put(watch, "b.jpg", enc(TEST_IM.resize((128, 96)), quality=40))
    assert {v[0] for v in levels(watch.scan_once()).values()} == {"alert"}
    assert not (watch.control_dir / W.STOP_FILE).exists()


def test_pool_image_is_derivative_not_stop(watch):
    put(watch, "pool_resized.jpg", enc(POOL_IM.resize((200, 150)), quality=60))
    put(watch, "pool_png.png", enc(POOL_IM, "PNG"))
    f = levels(watch.scan_once())
    assert f and all(v == ("info", "pool-derivative") for v in f.values()), f
    assert not (watch.control_dir / W.STOP_FILE).exists()


@pytest.mark.parametrize("bits,expected", [(0, ("alert", "phash-test-near")), (2, ("alert", "phash-test-near")),
                                           (3, ("alert", "phash-test-near")), (6, ("alert", "phash-test-near")),
                                           (7, None), (20, None)])
def test_phash_distance_bands(tmp_path, corpus_dict, bits, expected):
    """Register a test pHash exactly `bits` away from the image, so the Hamming distance is exact."""
    d = dict(corpus_dict, raw_sha256=[], phash={"pool": [], "test": [f"{int(ph(TEST_IM), 16) ^ ((1 << bits) - 1):016x}"]})
    (tmp_path / "ws").mkdir()
    w = W.Watcher(tmp_path / "ws", wc.Corpus(d), tmp_path / "st", tmp_path / "ctl")
    put(w, "i.png", enc(TEST_IM, "PNG"))
    f = levels(w.scan_once())
    assert f.get("i.png") == expected
    assert (w.control_dir / W.STOP_FILE).exists() == (expected is not None and expected[0] == "stop")


def test_optional_phash_stop_and_exact_pool_stop(tmp_path, corpus_dict):
    ws = tmp_path / "ws"
    ws.mkdir()
    w = W.Watcher(ws, wc.Corpus(corpus_dict), tmp_path / "st", tmp_path / "ctl", phash_stop_distance=2)
    put(w, "near.png", enc(TEST_IM, "PNG"))
    assert levels(w.scan_once()) == {"near.png": ("stop", "phash-test")}
    assert (w.control_dir / W.STOP_FILE).exists()
    put(w, "pool.jpg", POOL_JPG)
    assert levels(w.scan_once()) == {"pool.jpg": ("stop", "sha256")}


def test_normalized_hash_stops_even_if_phash_is_pool_only(tmp_path, corpus_dict):
    png = enc(POOL_IM, "PNG")
    d = dict(corpus_dict, raw_sha256=[], normalized_sha256=[sha(png)],
             phash={"pool": [ph(POOL_IM)], "test": []})
    (tmp_path / "ws").mkdir()
    w = W.Watcher(tmp_path / "ws", wc.Corpus(d), tmp_path / "st", tmp_path / "ctl")
    put(w, "pool.png", png)
    assert levels(w.scan_once()) == {"pool.png": ("stop", "sha256")}
    assert (w.control_dir / W.STOP_FILE).exists()


def test_pool_beyond_band_is_clean_and_ambiguous_prefers_test(tmp_path, corpus_dict):
    h = int(ph(TEST_IM), 16)
    d = dict(corpus_dict, raw_sha256=[], phash={"pool": [f"{h:016x}"], "test": [f"{h ^ 0b1111:016x}"]})
    (tmp_path / "ws").mkdir()
    w = W.Watcher(tmp_path / "ws", wc.Corpus(d), tmp_path / "st", tmp_path / "ctl")
    put(w, "i.png", enc(TEST_IM, "PNG"))  # 0 from pool, 4 from test: alert, not mere pool-derivative
    assert levels(w.scan_once()) == {"i.png": ("alert", "phash-test-near")}


def test_basenames_stop_needs_three_distinct(watch):
    put(watch, "two.txt", " ".join(NAMES[:2]).encode())
    put(watch, "dups.txt", ((NAMES[0] + "\n") * 10).encode())
    assert watch.scan_once() == []
    put(watch, "three.csv", ("\n".join(f"{n},1" for n in NAMES[:3])).encode())
    assert levels(watch.scan_once()) == {"three.csv": ("stop", "basenames")}


def test_archive_and_nested_detection(watch):
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("inner/t.jpg", TEST_JPG)
    put(watch, "data.zip", z.getvalue())
    z2 = io.BytesIO()
    with zipfile.ZipFile(z2, "w") as zf:
        zf.writestr("p.jpg", POOL_JPG)
    put(watch, "pool.zip", z2.getvalue())
    f = levels(watch.scan_once())
    assert f["data.zip"][0] == "stop"
    assert f["pool.zip"] == ("stop", "sha256")


def test_carved_and_archive_hash(watch):
    blob = b"PAR1" + os.urandom(100) + TEST_JPG + os.urandom(100)
    put(watch, "blob.parquet", blob)
    put(watch, "pool.blob", b"xx" + POOL_JPG + b"yy")
    put(watch, "arc.bin", b"archive-bytes")
    watch.corpus.archive.add(sha(b"archive-bytes"))
    f = levels(watch.scan_once())
    assert f["blob.parquet"][0] == "stop"
    assert f["pool.blob"] == ("stop", "sha256")
    assert f["arc.bin"] == ("stop", "sha256-archive")


def test_blob_containing_pool_does_not_hide_test(watch):
    put(watch, "mix.bin", b"a" + POOL_JPG + b"b" + TEST_JPG + b"c")
    assert levels(watch.scan_once())["mix.bin"][0] == "stop"


def test_base64_embedded_image(watch):
    put(watch, "e.json", json.dumps({"img": base64.b64encode(TEST_JPG).decode()}).encode())
    assert levels(watch.scan_once())["e.json"][0] == "stop"


def test_unscannable_is_alert_and_symlinks_ignored(watch, tmp_path):
    put(watch, "broken.jpg", b"\xff\xd8\xff\xe0 not a jpeg")
    (tmp_path / "outside.jpg").write_bytes(TEST_JPG)
    (watch.workspace / "link.jpg").symlink_to(tmp_path / "outside.jpg")
    f = levels(watch.scan_once())
    assert f == {"broken.jpg": ("alert", "unscannable-image-undecodable")}


def test_incremental_cache_and_rescan_on_change(watch, monkeypatch):
    p = put(watch, "a.jpg", enc(OTHER_IM))
    watch.scan_once()
    calls = []
    orig = watch.scan_file
    monkeypatch.setattr(watch, "scan_file", lambda path, size: calls.append(path) or orig(path, size))
    assert watch.scan_once() == [] and calls == []  # unchanged: not re-read
    time.sleep(0.01)
    p.write_bytes(TEST_JPG)
    assert levels(watch.scan_once()) == {"a.jpg": ("stop", "sha256")} and len(calls) == 1
    assert watch.scan_once() == [] and len(calls) == 1  # finding is not re-reported
    p.unlink()
    watch.scan_once()
    assert "a.jpg" not in watch.cache


def test_oversize_file_is_alert(watch):
    watch.max_file = 1000
    put(watch, "big.bin", b"x" * 2000)
    assert levels(watch.scan_once()) == {"big.bin": ("alert", "unscannable-size")}


def test_logs_never_contain_corpus_or_content(watch, corpus_dict):
    put(watch, "t.jpg", TEST_JPG)
    put(watch, "n.txt", " ".join(NAMES[:4]).encode())
    watch.scan_once()
    log = (watch.state_dir / "watcher.jsonl").read_text()
    for secret in [*corpus_dict["raw_sha256"], ph(TEST_IM), ph(POOL_IM), ARCHIVE_SHA, *NAMES]:
        assert secret not in log
    assert all(json.loads(line)["run_id"] == "r1" for line in log.splitlines())
    assert (watch.state_dir / "watcher.jsonl").stat().st_mode & 0o077 == 0


def test_cli_once_and_sigusr1(tmp_path, corpus_dict):
    ws, ctl, st = tmp_path / "ws", tmp_path / "ctl", tmp_path / "st"
    ws.mkdir()
    (tmp_path / "c.json").write_text(json.dumps(corpus_dict))
    base = [sys.executable, "-m", "infra.watcher", "--workspace", str(ws), "--corpus", str(tmp_path / "c.json"),
            "--state-dir", str(st), "--control-dir", str(ctl)]
    assert subprocess.run(base + ["--once"]).returncode == 0
    (ws / "x.jpg").write_bytes(TEST_JPG)
    assert subprocess.run(base + ["--once"]).returncode == 3
    assert json.loads((ctl / W.STOP_FILE).read_text())["file"] == "x.jpg"
    (ctl / W.STOP_FILE).unlink()
    (ws / "x.jpg").unlink()
    # long interval: only SIGUSR1 can trigger the second scan
    proc = subprocess.Popen(base + ["--interval", "3600"])
    try:
        time.sleep(4)
        (ws / "y.jpg").write_bytes(TEST_JPG)
        proc.send_signal(signal.SIGUSR1)
        for _ in range(60):
            if (ctl / W.STOP_FILE).exists():
                break
            time.sleep(0.5)
        assert json.loads((ctl / W.STOP_FILE).read_text())["file"] == "y.jpg"
    finally:
        proc.kill()
        proc.wait()


def test_bad_corpus_exits_nonzero(tmp_path):
    (tmp_path / "c.json").write_text("{}")
    r = subprocess.run([sys.executable, "-m", "infra.watcher", "--workspace", str(tmp_path), "--corpus",
                        str(tmp_path / "c.json"), "--state-dir", str(tmp_path / "s"), "--control-dir",
                        str(tmp_path / "c"), "--once"])
    assert r.returncode == 2
