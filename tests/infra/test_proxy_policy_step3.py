"""Unit tests for the policy functions with a synthetic hash corpus (no Docker)."""
import base64
import bz2
import gzip
import hashlib
import io
import lzma
import random
import tarfile
import zipfile

import imagehash
import pytest
from PIL import Image, ImageDraw

from infra.proxy import wsp_content as wc
from infra.proxy import wsp_policy as wp


def make_image(seed, size=(256, 192)):
    rnd = random.Random(seed)
    im = Image.new("L", size, rnd.randrange(40, 200))
    d = ImageDraw.Draw(im)
    for _ in range(25):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        d.ellipse([x, y, x + rnd.randrange(10, 90), y + rnd.randrange(10, 90)], fill=rnd.randrange(256))
    return im.convert("RGB")


def encode(im, fmt="JPEG", **kw):
    b = io.BytesIO()
    im.save(b, format=fmt, **kw)
    return b.getvalue()


def norm_sha(im):
    return hashlib.sha256(encode(im, "PNG", optimize=False)).hexdigest()


SECRET = make_image(1)
OTHER = make_image(99)
SECRET_JPEG = encode(SECRET, quality=92)
NAMES = [f"{200000 + i}-{i % 3 + 1}.jpg" for i in range(10)]


@pytest.fixture(scope="module")
def corpus():
    return wc.Corpus({
        "archive_sha256": "a" * 64,
        "raw_sha256": [hashlib.sha256(SECRET_JPEG).hexdigest()],
        "normalized_sha256": [norm_sha(SECRET)],
        "phash": {"pool": [str(imagehash.phash(SECRET))], "test": ["0" * 16]},
        "basenames": NAMES,
    })


def scan(data, corpus, **kw):
    return wc.scan_body(data, corpus, wc.Limits(**kw))


def zipped(files, **kw):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in files.items():
            z.writestr(n, d)
    return b.getvalue()


def tarred(files):
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w") as t:
        for n, d in files.items():
            i = tarfile.TarInfo(n)
            i.size = len(d)
            t.addfile(i, io.BytesIO(d))
    return b.getvalue()


def test_clean_image_and_text(corpus):
    assert scan(encode(OTHER), corpus) is None
    assert scan(b"hello world, nothing here", corpus) is None
    assert scan(b"", corpus) is None


def test_raw_hash(corpus):
    assert scan(SECRET_JPEG, corpus) == "sha256"


def test_archive_hash(corpus):
    c = wc.Corpus({"archive_sha256": hashlib.sha256(b"ARCHIVE").hexdigest(), "raw_sha256": [],
                   "normalized_sha256": [], "phash": {"pool": [], "test": []}, "basenames": []})
    assert scan(b"ARCHIVE", c) == "sha256"


def test_normalized_hash_different_container(corpus):
    # Same pixels, different encoding (lossless PNG): normalized sha matches.
    assert scan(encode(SECRET, "PNG"), corpus) in ("sha256", "phash", "sha256-normalized")
    c = wc.Corpus({"archive_sha256": "a" * 64, "raw_sha256": [], "normalized_sha256": [norm_sha(SECRET)],
                   "phash": {"pool": [], "test": []}, "basenames": []})
    assert scan(encode(SECRET, "PNG"), c) == "sha256"  # already the normalized bytes
    assert scan(encode(SECRET, "BMP"), c) == "sha256-normalized"


def test_phash_reencoded_and_resized(corpus):
    assert scan(encode(SECRET, quality=40), corpus) == "phash"
    small = SECRET.resize((128, 96))
    assert scan(encode(small, quality=70), corpus) == "phash"
    assert scan(encode(SECRET.resize((400, 300)), "PNG"), corpus) == "phash"


def test_phash_threshold():
    base = int(str(imagehash.phash(SECRET)), 16)
    def c_for(flips):
        v = base
        for i in range(flips):
            v ^= 1 << i
        return wc.Corpus({"archive_sha256": "a" * 64, "raw_sha256": [], "normalized_sha256": [],
                          "phash": {"pool": [], "test": [f"{v:016x}"]}, "basenames": []})
    im = encode(SECRET, quality=90)
    assert scan(im, c_for(4)) == "phash"
    assert scan(im, c_for(5)) is None


def test_inside_zip_and_nested(corpus):
    assert scan(zipped({"a/b.jpg": SECRET_JPEG}), corpus) == "sha256"
    assert scan(zipped({"x.txt": b"hi", "b.jpg": encode(SECRET, quality=50)}), corpus) == "phash"
    assert scan(zipped({"x.txt": b"hi", "b.jpg": encode(OTHER)}), corpus) is None
    tgz = gzip.compress(tarred({"d/inner.zip": zipped({"p.jpg": SECRET_JPEG})}))
    assert scan(tgz, corpus) == "sha256"   # gz -> tar -> zip -> jpg: depth 3 levels opened


@pytest.mark.parametrize("comp", [gzip.compress, bz2.compress, lzma.compress])
def test_single_stream_compressors(corpus, comp):
    assert scan(comp(SECRET_JPEG), corpus) == "sha256"


def test_zstd(corpus):
    try:
        from compression import zstd
        blob = zstd.compress(SECRET_JPEG)
    except ImportError:
        zstandard = pytest.importorskip("zstandard")
        blob = zstandard.ZstdCompressor().compress(SECRET_JPEG)
    assert scan(blob, corpus) == "sha256"


def test_depth_limit(corpus):
    inner = SECRET_JPEG
    for _ in range(3):
        inner = zipped({"n.zip": inner})
    assert scan(inner, corpus) == "sha256"          # 3 levels opened
    assert scan(zipped({"n.zip": inner}), corpus) == "archive-depth"   # 4 levels


def test_encrypted_zip_blocked(corpus):
    data = bytearray(zipped({"s.bin": b"x" * 10}))
    data[6] |= 1                        # local header general-purpose flag: encrypted
    cd = data.index(b"PK\x01\x02")
    data[cd + 8] |= 1                   # central directory flag
    assert scan(bytes(data), corpus) == "archive-encrypted"


def test_uncompressed_limit(corpus):
    bomb = gzip.compress(b"\0" * 5_000_000)
    assert scan(bomb, corpus, max_uncompressed=1_000_000) == "archive-limit"
    assert scan(bomb, corpus) is None
    z = zipped({"a": b"\0" * 600_000, "b": b"\0" * 600_000})
    assert scan(z, corpus, max_uncompressed=1_000_000) == "archive-limit"


def test_unreadable_archive_blocked(corpus):
    assert scan(b"PK\x03\x04" + b"garbage" * 50, corpus) == "archive-unreadable"
    assert scan(b"\x1f\x8b" + b"garbage" * 50, corpus) == "archive-unreadable"


def test_size_limit_fail_closed(corpus):
    assert scan(b"x" * 101, corpus, max_body=100) == "size-limit"


def test_carved_from_parquet_like_blob(corpus):
    rnd = random.Random(5)
    junk = lambda n: bytes(rnd.randrange(256) for _ in range(n))
    blob = b"PAR1" + junk(3000) + b"\0" + SECRET_JPEG + junk(500) + encode(OTHER) + b"\0\0" + junk(100)
    assert scan(blob, corpus) == "sha256"                      # exact stream hash
    re_enc = b"PAR1" + junk(2000) + b"\0" + encode(SECRET, quality=35) + junk(300)
    assert scan(re_enc, corpus) == "phash"
    png = b"ARROW1\0\0" + junk(100) + encode(SECRET, "PNG") + junk(50)
    assert scan(png, corpus) in ("phash", "sha256")
    clean = b"PAR1" + junk(3000) + b"\0" + encode(OTHER) + junk(100) + encode(OTHER, "PNG")
    assert scan(clean, corpus) is None


def test_appended_image_in_image(corpus):
    assert scan(encode(OTHER) + SECRET_JPEG, corpus) == "sha256"


def test_carve_limit(corpus):
    blob = b"\0" + (b"\xff\xd8\xff" + b"\0" * 20) * 30
    assert scan(blob, corpus, max_carved=10) == "carve-limit"


def test_base64_embedded(corpus):
    doc = b'{"image": "' + base64.b64encode(SECRET_JPEG) + b'"}'
    assert scan(doc, corpus) == "sha256"
    doc = b"data:image/jpeg;base64," + base64.b64encode(encode(SECRET, quality=40))
    assert scan(doc, corpus) == "phash"


def test_pixel_limit_and_undecodable(corpus):
    assert scan(encode(OTHER), corpus, max_pixels=1000) == "image-pixel-limit"
    assert scan(b"\xff\xd8\xff\xe0" + b"junk" * 100, corpus) == "image-undecodable"


def test_basenames(corpus):
    two = " ".join(NAMES[:2]).encode()
    assert scan(two, corpus) is None
    assert scan(two + b" and /path/" + NAMES[5].encode(), corpus) == "basenames"
    assert scan(("\n".join(NAMES[:3])).upper().encode(), corpus) == "basenames"
    assert scan(b"\n".join(n.encode() for n in NAMES[:2]) + b"\n" + NAMES[0].encode() * 3, corpus) is None  # distinct
    assert scan(b"1-1.jpg 2-1.jpg 3-1.jpg", corpus) is None       # not original names
    assert scan(zipped({n: b"x" for n in NAMES[:3]}), corpus) == "basenames"
    assert scan(tarred({n: b"x" for n in NAMES[:3]}), corpus) == "basenames"
    assert scan(b"\0\0" + b" ".join(n.encode() for n in NAMES[:4]), corpus) == "basenames"   # binary blob too


def test_upload_basenames_only(corpus):
    assert wc.scan_upload(" ".join(NAMES[:3]).encode(), corpus) == "basenames"
    assert wc.scan_upload(SECRET_JPEG, corpus) is None   # uploads: basenames check only
    assert wc.scan_upload(b"", corpus) is None


# ------------------------------------------------------------------ URL rules
@pytest.mark.parametrize("url,rule", [
    ("https://FIGSHARE.COM//articles/dataset/x/30335941", "mfxr-figshare"),
    ("https://figshare.com/articles/dataset/x/30335941/1", "mfxr-figshare"),
    ("https://api.figshare.com/v2/file%73/66766667", "mfxr-figshare"),
    ("https://ndownloader.figshare.com/files/66766667", "mfxr-figshare"),
    ("https://ndownloader.figshare.com/files/66766667?private=1", "mfxr-figshare"),
    ("https://figshare-production.s3.eu-west-1.amazonaws.com/x/30335941", "mfxr-figshare"),
    ("https://api.figshare.com/v2/articles/30335941/files", "mfxr-figshare"),
    ("https://doi.org/10.6084%2Fm9.figshare.30335941", "mfxr-doi"),
    ("https://doi.org/10.6084%252Fm9.figshare.30335941.v1", "mfxr-doi"),
    ("https://dx.doi.org/10.6084/M9.FIGSHARE.30335941", "mfxr-doi"),
    ("https://github.com/Ninglitony//Benchmark-for-MFXR", "mfxr-repository"),
    ("https://github.com/./ninglitony/./benchmark-for-mfxr", "mfxr-repository"),
    ("https://github.com/ninglitony%2FBenchmark-for-MFXR/archive/main.zip", "mfxr-repository"),
    ("https://github.com\\ninglitony\\Benchmark-for-MFXR", "mfxr-repository"),
    ("https://api.github.com/repos/ninglitony/Benchmark-for-MFXR/zipball", "mfxr-repository"),
    ("https://raw.githubusercontent.com/ninglitony/Benchmark-for-MFXR/main/x", "mfxr-repository"),
    ("https://codeload.github.com/ninglitony/Benchmark-for-MFXR/zip/refs/heads/main", "mfxr-repository"),
    ("https://objects.githubusercontent.com/ninglitony/benchmark-for-mfxr/x", "mfxr-repository"),
    ("https://gist.github.com/ninglitony/benchmark-for-mfxr", "mfxr-repository"),
    ("https://cdn.jsdelivr.net/gh/ninglitony/Benchmark-for-MFXR@main/a.jpg", "mfxr-repository"),
    ("https://rawcdn.githack.com/ninglitony/Benchmark-for-MFXR/x/y", "mfxr-repository"),
    ("https://statically.io/gh/ninglitony/benchmark-for-mfxr", "mfxr-repository"),
    ("https://some-relay.example/fetch?u=https%3A%2F%2Fgithub.com%2Fninglitony%2Fbenchmark-for-mfxr", "mfxr-repository"),
    ("https://r.jina.ai/https://example.com", "hosted-relay"),
    ("https://s.jina.ai/query", "hosted-relay"),
    ("https://web.archive.org/web/2024/https://example.com", "hosted-relay"),
    ("https://translate.google.com/translate?u=x", "hosted-relay"),
    ("https://api.firecrawl.dev/v1/scrape", "hosted-relay"),
    ("https://api.tavily.com/extract", "hosted-relay"),
    ("https://api.tavily.com//EXTRACT", "hosted-relay"),
    ("ftp://example.com/x", "invalid-url"),
    ("https:///nohost", "invalid-url"),
])
def test_denied_urls(url, rule):
    assert wp.url_rule(url, wp.load_rules()) == rule


@pytest.mark.parametrize("url", [
    "https://pypi.org/simple/", "https://huggingface.co/skhoha/SKELEX/resolve/main/config.json",
    "https://github.com/pytorch/pytorch", "https://api.tavily.com/search",
    "https://files.pythonhosted.org/packages/x/y.whl", "https://figshare.com/articles/dataset/other/12345",
])
def test_allowed_urls_not_matched(url):
    assert wp.url_rule(url, wp.load_rules()) is None


# ------------------------------------------------------------- destinations
@pytest.mark.parametrize("ip", [
    "127.0.0.1", "127.1.2.3", "10.0.0.5", "172.17.0.1", "172.31.255.255", "192.168.1.1", "169.254.169.254",
    "100.64.0.1", "100.100.100.200", "224.0.0.1", "0.0.0.0", "255.255.255.255", "240.0.0.1", "198.18.0.1",
    "::1", "fe80::1", "fc00::1", "fd00:ec2::254", "ff02::1", "::ffff:10.0.0.1", "::ffff:127.0.0.1",
    "64:ff9b::7f00:1", "2002:7f00:1::", "::", "not-an-ip",
])
def test_private_ips_refused(ip):
    assert wp.ip_refused(ip)


@pytest.mark.parametrize("ip", ["1.1.1.1", "8.8.8.8", "151.101.0.223", "2606:4700:4700::1111"])
def test_public_ips_allowed(ip):
    assert not wp.ip_refused(ip)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "2130706433", "0x7f.1", "017700000001",
                                  "10.1.2.3", "[::1]".strip("[]"), "0", "127.1"])
def test_private_hosts_rejected_by_resolution(host):
    assert wp.destination_rule(host, 443) in ("private-destination", "resolve-failed")


def test_test_mode_exemption_requires_both_flags(monkeypatch):
    monkeypatch.setenv("WSP_TEST_ALLOW_IPS", "10.9.9.9")
    assert wp.ip_refused("10.9.9.9")
    monkeypatch.setenv("WSP_TEST_MODE", "1")
    assert not wp.ip_refused("10.9.9.9")
    assert wp.ip_refused("10.9.9.8")
    assert wp.ip_refused("127.0.0.1")


def test_mfxr_derived_repository_denied_on_any_host():
    from infra.proxy.wsp_policy import load_rules, url_rule
    rules = load_rules()
    for url in ("https://github.com/surajbi2/birs-radiograph-adaptation",
                "https://raw.githubusercontent.com/surajbi2/birs-radiograph-adaptation/main/x.csv",
                "https://api.github.com/repos/surajbi2/birs-radiograph-adaptation/contents"):
        assert url_rule(url, rules) == "mfxr-derived-repository"
    assert url_rule("https://github.com/surajbi2", rules) is None
