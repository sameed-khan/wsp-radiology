"""Content inspection for the WSP proxy (spec section 4, policy item 3).

Pure functions, no mitmproxy dependency, so they are unit-testable on the host.
Every failure mode (undecodable image, encrypted/over-limit archive, unreadable
archive, limit exceeded) raises Blocked: decisions fail closed.
"""
from __future__ import annotations

import base64
import bz2
import gzip
import hashlib
import io
import json
import lzma
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import imagehash

try:  # Proxy image (py3.13) ships `zstandard`; py3.14 has compression.zstd.
    import zstandard as _zstandard
except ImportError:  # pragma: no cover
    _zstandard = None
try:
    from compression import zstd as _zstd314
except ImportError:
    _zstd314 = None

GIB = 1 << 30


class Blocked(Exception):
    def __init__(self, rule: str):
        super().__init__(rule)
        self.rule = rule


@dataclass(frozen=True)
class Limits:
    max_body: int = 4 * GIB          # larger bodies are blocked (fail closed)
    max_uncompressed: int = 20 * GIB  # total decompressed bytes per body
    max_member: int = 4 * GIB        # single decompressed member held in memory
    max_depth: int = 3               # nested container levels that may be opened
    max_carved: int = 20_000         # carved-image candidates per body
    max_members: int = 100_000       # archive members per body
    max_pixels: int = 100_000_000
    phash_block: int = 4             # Hamming distance <= this -> block
    basename_block: int = 3          # distinct original basenames -> block


class Corpus:
    def __init__(self, data: dict):
        self.archive = {str(data["archive_sha256"]).lower()}
        self.raw = {h.lower() for h in data["raw_sha256"]}
        self.normalized = {h.lower() for h in data["normalized_sha256"]}
        self.phash_pool = [int(h, 16) for h in data["phash"]["pool"]]
        self.phash_test = [int(h, 16) for h in data["phash"]["test"]]
        self.basenames = {b.lower() for b in data["basenames"]}
        for h in self.raw | self.normalized | self.archive:
            if len(h) != 64:
                raise ValueError("bad sha256 in corpus")
        self._phash = np.array(self.phash_pool + self.phash_test, dtype=np.uint64)
        self.hashes_sha = self.raw | self.normalized | self.archive

    @classmethod
    def load(cls, path) -> "Corpus":
        return cls(json.loads(Path(path).read_text()))

    def min_phash_distance(self, value: int) -> int:
        if not len(self._phash):
            return 64
        x = self._phash ^ np.uint64(value)
        return int(np.bitwise_count(x).min())


@dataclass
class State:
    limits: Limits
    uncompressed: int = 0
    carved: int = 0
    carve_bytes: int = 0
    members: int = 0
    names: set = field(default_factory=set)

    def charge(self, n: int):
        self.uncompressed += n
        if self.uncompressed > self.limits.max_uncompressed:
            raise Blocked("archive-limit")


# ---------------------------------------------------------------- sniffing
PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"
JPEG_SOI = b"\xff\xd8\xff"
JPEG_EOI = b"\xff\xd9"


def sniff(data: bytes) -> str | None:
    head = data[:16]
    if head.startswith(JPEG_SOI):
        return "image"
    if head.startswith(PNG_SIG) or head.startswith((b"GIF87a", b"GIF89a", b"BM", b"II*\x00", b"MM\x00*")):
        return "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return "zip"
    if head.startswith(b"\x1f\x8b"):
        return "gz"
    if head.startswith(b"BZh"):
        return "bz2"
    if head.startswith(b"\xfd7zXZ\x00"):
        return "xz"
    if head.startswith(b"\x28\xb5\x2f\xfd"):
        return "zstd"
    if data[257:262] == b"ustar":
        return "tar"
    return None


def is_texty(data: bytes) -> bool:
    return b"\0" not in data[:8192]


# ------------------------------------------------------------------ basenames
_EXT = re.compile(rb"\.(?:jpe?g|bmp)", re.I)
_TOKEN = re.compile(rb"[\w]+-[\w]+$")


def basenames_in(data: bytes, corpus: Corpus) -> set[str]:
    found = set()
    for m in _EXT.finditer(data):
        start = max(0, m.start() - 64)
        t = _TOKEN.search(data[start:m.start()])
        if t:
            name = (t.group(0) + m.group(0)).decode("ascii", "ignore").lower()
            if name in corpus.basenames:
                found.add(name)
    return found


def check_basenames(data: bytes, corpus: Corpus, state: State):
    state.names |= basenames_in(data, corpus)
    if len(state.names) >= state.limits.basename_block:
        raise Blocked("basenames")


# --------------------------------------------------------------------- images
def check_image(data: bytes, corpus: Corpus, state: State, strict: bool):
    """Decode with pixel limit, compare normalized sha and pHash.

    strict=False (carved candidates): undecodable data is ignored.
    """
    lim = state.limits
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.width * im.height > lim.max_pixels:
                raise Blocked("image-pixel-limit")
            im.load()
            oriented = ImageOps.exif_transpose(im).convert("RGB")
            clean = Image.new("RGB", oriented.size)
            clean.paste(oriented)
    except Blocked:
        raise
    except Exception:
        if strict:
            raise Blocked("image-undecodable")
        return
    if corpus.normalized:
        out = io.BytesIO()
        clean.save(out, format="PNG", optimize=False)
        if hashlib.sha256(out.getvalue()).hexdigest() in corpus.normalized:
            raise Blocked("sha256-normalized")
    value = int(str(imagehash.phash(clean)), 16)
    if corpus.min_phash_distance(value) <= lim.phash_block:
        raise Blocked("phash")


def _positions(data: bytes, needle: bytes, cap: int) -> list[int]:
    out, i = [], data.find(needle)
    while i != -1:
        out.append(i)
        if len(out) > cap:
            raise Blocked("carve-limit")
        i = data.find(needle, i + 1)
    return out


def carve_images(data: bytes, corpus: Corpus, state: State):
    lim = state.limits
    cap = lim.max_carved
    from bisect import bisect_left
    for sig, end, end_tail in ((JPEG_SOI, JPEG_EOI, 2), (PNG_SIG, PNG_END, 8)):
        starts = _positions(data, sig, cap)
        if not starts:
            continue
        ends = _positions(data, end, cap * 4)
        for s in starts:
            state.carved += 1
            if state.carved > cap:
                raise Blocked("carve-limit")
            k = bisect_left(ends, s + len(sig))
            for e in ends[k:k + 3]:
                stop = e + end_tail
                if s == 0 and stop == len(data):
                    break  # the whole body, already inspected as a body
                state.carve_bytes += stop - s
                if state.carve_bytes > lim.max_uncompressed:
                    raise Blocked("carve-limit")
                chunk = data[s:stop]
                scan(chunk, corpus, state, depth=lim.max_depth, carve=False, strict_image=False)
                if _decodes(chunk):
                    break


def _decodes(chunk: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(chunk)) as im:
            im.verify()
        return True
    except Exception:
        return False


# ------------------------------------------------------------------- archives
def _read_capped(fileobj, cap: int) -> bytes:
    buf = bytearray()
    while True:
        chunk = fileobj.read(1 << 24)
        if not chunk:
            return bytes(buf)
        buf += chunk
        if len(buf) > cap:
            raise Blocked("archive-limit")


def _zstd_file(raw: bytes):
    if _zstd314 is not None:
        return _zstd314.ZstdFile(io.BytesIO(raw))
    if _zstandard is not None:
        return _zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw), read_across_frames=True)
    raise Blocked("archive-unreadable")


def _open_archive(kind: str, data: bytes, corpus: Corpus, state: State, depth: int):
    lim = state.limits
    if depth >= lim.max_depth:
        raise Blocked("archive-depth")
    remaining = lambda: min(lim.max_member, lim.max_uncompressed - state.uncompressed)
    try:
        if kind == "zip":
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                infos = zf.infolist()
                if len(infos) + state.members > lim.max_members:
                    raise Blocked("archive-limit")
                state.members += len(infos)
                for info in infos:
                    if info.flag_bits & 0x1:
                        raise Blocked("archive-encrypted")
                check_basenames("\n".join(i.filename for i in infos).encode("utf-8", "ignore"), corpus, state)
                for info in infos:
                    if info.is_dir():
                        continue
                    if info.file_size > remaining():
                        raise Blocked("archive-limit")
                    with zf.open(info) as f:
                        member = _read_capped(f, remaining())
                    state.charge(len(member))
                    scan(member, corpus, state, depth + 1)
        elif kind == "tar":
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tf:
                for info in tf:
                    state.members += 1
                    if state.members > lim.max_members:
                        raise Blocked("archive-limit")
                    check_basenames(info.name.encode("utf-8", "ignore"), corpus, state)
                    if not info.isfile():
                        continue
                    if info.size > remaining():
                        raise Blocked("archive-limit")
                    member = _read_capped(tf.extractfile(info), remaining())
                    state.charge(len(member))
                    scan(member, corpus, state, depth + 1)
        else:
            opener = {"gz": lambda: gzip.GzipFile(fileobj=io.BytesIO(data)),
                      "bz2": lambda: bz2.BZ2File(io.BytesIO(data)),
                      "xz": lambda: lzma.LZMAFile(io.BytesIO(data)),
                      "zstd": lambda: _zstd_file(data)}[kind]
            with opener() as f:
                inner = _read_capped(f, remaining())
            state.charge(len(inner))
            scan(inner, corpus, state, depth + 1)
    except Blocked:
        raise
    except Exception:
        raise Blocked("archive-unreadable")


# ------------------------------------------------------------------ base64
_B64 = re.compile(rb"[A-Za-z0-9+/_-]{2000,}={0,2}")


def _scan_base64(data: bytes, corpus: Corpus, state: State, depth: int):
    n = 0
    for m in _B64.finditer(data):
        n += 1
        if n > state.limits.max_carved:
            raise Blocked("carve-limit")
        run = m.group(0)
        try:
            raw = base64.b64decode(run + b"=" * (-len(run) % 4), altchars=b"-_" if (b"-" in run or b"_" in run) else None)
        except Exception:
            continue
        if sniff(raw) or JPEG_SOI in raw[:16]:
            state.charge(len(raw))
            scan(raw, corpus, state, depth + 1)


# ---------------------------------------------------------------------- scan
def scan(data: bytes, corpus: Corpus, state: State, depth: int = 0, carve: bool = True,
         strict_image: bool = True):
    """Raise Blocked if `data` (or anything nested) matches the corpus."""
    if len(data) > state.limits.max_member and depth:
        raise Blocked("archive-limit")
    if hashlib.sha256(data).hexdigest() in corpus.hashes_sha:
        raise Blocked("sha256")
    kind = sniff(data)
    if kind == "image":
        check_image(data, corpus, state, strict_image)
    elif kind:
        _open_archive(kind, data, corpus, state, depth)
        return
    else:
        # Stricter than the spec's "text bodies": binary blobs (parquet, arrow)
        # are also searched for original basenames.
        check_basenames(data, corpus, state)
        if is_texty(data) and depth < state.limits.max_depth:
            _scan_base64(data, corpus, state, depth)
    if carve:
        carve_images(data, corpus, state)


def scan_body(data: bytes, corpus: Corpus, limits: Limits = Limits()) -> str | None:
    """Response-body scan. Returns a rule id when blocked, None when clean."""
    if len(data) > limits.max_body:
        return "size-limit"
    try:
        scan(data, corpus, State(limits))
    except Blocked as e:
        return e.rule
    except Exception:
        return "scan-error"
    return None


def scan_upload(data: bytes, corpus: Corpus, limits: Limits = Limits()) -> str | None:
    """Request bodies: basenames check only (spec)."""
    if len(data) > limits.max_body:
        return "size-limit"
    if not data:
        return None
    try:
        check_basenames(data, corpus, State(limits))
    except Blocked as e:
        return e.rule
    except Exception:
        return "scan-error"
    return None
