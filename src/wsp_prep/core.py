from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import imagehash
import requests
from PIL import Image, ImageOps

MFXR_SHA256 = "80f959a9a51ff7c441459bcbbfa174d084d50126685f4ca980c8e84cfd7cadfe"
MFXR_MD5 = "7867f6403ce719dc45bfefd4b1892a38"
MFXR_ARTICLE = 30335941
MFXR_FILE = 66766667
MODELS = {
    "skhoha/SKELEX": "368cae7b05cf649e6dbcddae9a7f00ea4b14bb8e",
    "google/medsiglip-448": "9cea28a1a1195f665105faa6e8544c112fd960a4",
    "facebook/dinov3-vitl16-pretrain-lvd1689m": "ea8dc2863c51be0a264bab82070e3e8836b02d51",
}
IMAGE_RE = re.compile(r"^[^/\\]+-([^/\\]+)\.(?:jpg|jpeg|bmp)$", re.I)


def ensure_private(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_download(url: str, target: Path, *, expected: dict[str, str] | None = None,
                    attempts: int = 3, session: requests.Session | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("downloads require an absolute HTTPS URL")
    client = session or requests.Session()
    for attempt in range(attempts):
        temp = target.with_name(f".{target.name}.{os.getpid()}.part")
        try:
            with client.get(url, stream=True, timeout=(30, 180)) as response:
                response.raise_for_status()
                with temp.open("wb") as out:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            out.write(chunk)
                    out.flush()
                    os.fsync(out.fileno())
            for algorithm, wanted in (expected or {}).items():
                if digest(temp, algorithm) != wanted.lower():
                    raise ValueError(f"{algorithm} integrity check failed for {target.name}")
            os.replace(temp, target)
            return
        except Exception:
            temp.unlink(missing_ok=True)
            if attempt + 1 == attempts:
                raise
            time.sleep(min(2**attempt, 8))


def figshare_file(article_id: int, file_id: int, version: int | None = None) -> dict:
    url = f"https://api.figshare.com/v2/articles/{article_id}"
    if version is not None:
        url += f"/versions/{version}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    article = response.json()
    matches = [f for f in article.get("files", []) if int(f["id"]) == file_id]
    if len(matches) != 1:
        raise ValueError(f"Figshare file {file_id} not found exactly once in article {article_id}")
    return {**matches[0], "article_id": article_id, "version": article.get("version")}


def fetch_mfxr(root: Path) -> Path:
    downloads = ensure_private(root / "data/locked/downloads")
    target = downloads / "MFXR.zip"
    if target.exists():
        check_mfxr(target)
        return target
    file = figshare_file(MFXR_ARTICLE, MFXR_FILE)
    if file.get("computed_md5") != MFXR_MD5 or file.get("supplied_md5") != MFXR_MD5:
        raise ValueError("MFXR Figshare MD5 does not match the approved source contract")
    atomic_download(file["download_url"], target,
                    expected={"md5": MFXR_MD5, "sha256": MFXR_SHA256})
    return target


def check_mfxr(path: Path) -> None:
    if digest(path, "sha256") != MFXR_SHA256:
        raise ValueError("MFXR archive SHA-256 mismatch")
    if digest(path, "md5") != MFXR_MD5:
        raise ValueError("MFXR archive MD5 mismatch")


def safe_zip_members(archive: zipfile.ZipFile):
    members = archive.infolist()
    if len(members) > 10000 or sum(m.file_size for m in members) > 40 * 1024**3:
        raise ValueError("archive resource limit exceeded")
    for member in members:
        if member.file_size > 100 * 1024**2:
            raise ValueError("archive member resource limit exceeded")
        name = member.filename.replace("\\", "/")
        path = PurePosixPath(name)
        mode = member.external_attr >> 16
        if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
            raise ValueError(f"unsafe archive path: {name!r}")
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink in archive: {name!r}")
        yield member, path


def load_image_bytes(data: bytes) -> Image.Image:
    import io
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.width * image.height > 100_000_000:
            raise ValueError("image pixel limit exceeded")
        oriented = ImageOps.exif_transpose(image).convert("RGB")
        clean = Image.new("RGB", oriented.size)
        clean.paste(oriented)
        return clean


EXPECTED_COUNTS = {"train/anomaly": 1794, "train/good": 1199, "test/anomaly": 999, "test/good": 594}


def validate_generation(generation: Path, archive_sha: str) -> dict:
    inventory = json.loads((generation / "data/locked/inventory.json").read_text())
    if inventory["archive_sha256"] != archive_sha or inventory["counts"] != EXPECTED_COUNTS:
        raise ValueError("generation archive or counts mismatch")
    counts, names, sources = {}, set(), set()
    pool = generation / "data/pool"
    for row in inventory["records"]:
        if row["source_path"] in sources:
            raise ValueError("duplicate source in inventory")
        sources.add(row["source_path"])
        key = row["split"] + "/" + row["label"]
        counts[key] = counts.get(key, 0) + 1
        if row["split"] == "train":
            name = row["anonymous_filename"]
            if not re.fullmatch(r"[0-9a-f]{32}\.png", name) or name in names:
                raise ValueError("invalid anonymous mapping")
            names.add(name)
            path = pool / name
            if path.is_symlink() or digest(path, "sha256") != row["normalized_sha256"]:
                raise ValueError("pool hash mismatch")
        elif "anonymous_filename" in row:
            raise ValueError("test image in pool mapping")
    if counts != EXPECTED_COUNTS or {p.name for p in pool.iterdir()} != names:
        raise ValueError("generation pool or inventory count mismatch")
    return {"image_count": len(inventory["records"]), "counts": counts,
            "prefix_patient_count": inventory["prefix_patient_count"], "prefix_map_status": "unreviewed"}


def inventory_archive(archive_path: Path, destination: Path, *, rebuild: bool = False) -> dict:
    check_mfxr(archive_path)
    archive_sha = digest(archive_path, "sha256")
    locked = ensure_private(destination / "data/locked")
    generations = ensure_private(locked / "generations")
    pool = destination / "data/pool"
    with (locked / "prepare.lock").open("a") as lock:
        os.chmod(locked / "prepare.lock", 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        if pool.is_symlink():
            target = pool.resolve(strict=True)
            generation = target.parent.parent
            if target.name != "pool" or target.parent.name != "data" or generation.parent != generations.resolve():
                raise ValueError("pool link does not reference a private generation")
            if not rebuild:
                return {**validate_generation(generation, archive_sha), "status": "reused"}
        elif pool.exists():
            if not rebuild:
                raise ValueError("unvalidated legacy pool: use --rebuild to quarantine it")
            quarantine = ensure_private(locked / "quarantine")
            legacy = quarantine / ("legacy-pool-" + os.urandom(16).hex())
            os.replace(pool, legacy)
            os.chmod(legacy, 0o700)
        generation = Path(tempfile.mkdtemp(prefix="generation-", dir=generations))
        os.chmod(generation, 0o700)
        try:
            _build_inventory(archive_path, generation)
            result = validate_generation(generation, archive_sha)
            temporary = destination / "data" / (".pool-" + os.urandom(16).hex())
            os.symlink(os.path.relpath(generation / "data/pool", temporary.parent), temporary)
            try:
                os.replace(temporary, pool)
            finally:
                temporary.unlink(missing_ok=True)
            return {**result, "status": "built"}
        except BaseException:
            shutil.rmtree(generation)
            raise


def _build_inventory(archive_path: Path, destination: Path) -> dict:
    """Write protected inventory and train pool from verified archive without extractall."""
    check_mfxr(archive_path)
    locked = ensure_private(destination / "data/locked")
    pool = ensure_private(destination / "data/pool")
    records, prefixes = [], {}
    count_by_split_label = {}
    with zipfile.ZipFile(archive_path) as archive:
        members = list(safe_zip_members(archive))
        for member, member_path in members:
            if member.is_dir() or member_path.suffix.lower() not in {".jpg", ".jpeg", ".bmp"}:
                continue
            parts = member_path.parts
            if len(parts) != 4 or parts[0] != "MFXR" or parts[1] not in {"train", "test"} or parts[2] not in {"anomaly", "good"}:
                continue
            match = IMAGE_RE.match(parts[3])
            if not match:
                raise ValueError(f"unexpected image filename format: {parts[3]!r}")
            raw = archive.read(member)
            image = load_image_bytes(raw)
            import io
            normalized = io.BytesIO()
            image.save(normalized, format="PNG", optimize=False)
            pixel_bytes = normalized.getvalue()
            split, label = parts[1], parts[2]
            record = {
                "source_path": "/".join(parts), "patient_prefix": parts[3].split("-", 1)[0],
                "view_suffix": match.group(1), "split": split, "label": label,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "normalized_sha256": hashlib.sha256(pixel_bytes).hexdigest(),
                "phash": str(imagehash.phash(image)), "size": [image.width, image.height],
            }
            count_by_split_label[f"{split}/{label}"] = count_by_split_label.get(f"{split}/{label}", 0) + 1
            prefixes.setdefault(record["patient_prefix"], set()).add(label)
            if split == "train":
                anonymous = f"{os.urandom(16).hex()}.png"
                record["anonymous_filename"] = anonymous
                output = pool / anonymous
                with output.open("xb") as stream:
                    stream.write(pixel_bytes)
                os.chmod(output, 0o600)
            records.append(record)
    if count_by_split_label != EXPECTED_COUNTS:
        raise ValueError("unexpected archive split/image counts")
    # This map is a hypothesis sourced from paper and filenames, not reviewed/eligible for sampling.
    proposal = [{"source_prefix": prefix, "labels": sorted(labels), "status": "unreviewed"}
                for prefix, labels in sorted(prefixes.items())]
    inventory = {"archive_sha256": digest(archive_path, "sha256"), "counts": count_by_split_label,
                 "image_count": len(records), "prefix_patient_count": len(prefixes),
                 "paper_patient_count": 1482, "prefix_count_discrepancy": len(prefixes) != 1482,
                 "patient_identity_basis": "filename prefixes; not independently confirmed",
                 "records": records}
    for path, value in ((locked / "inventory.json", inventory),
                        (locked / "prefix-map-proposal.json", proposal)):
        path.write_text(json.dumps(value, indent=2) + "\n")
        os.chmod(path, 0o600)
    return {"image_count": len(records), "counts": count_by_split_label,
            "prefix_patient_count": len(prefixes), "prefix_map_status": "unreviewed"}


def validate_patient_map(path: Path, inventory_path: Path) -> dict:
    data = json.loads(path.read_text())
    inventory = json.loads(inventory_path.read_text())
    if not isinstance(data, list) or not data:
        raise ValueError("patient map must be a nonempty JSON array")
    expected = {}
    for record in inventory["records"]:
        prefix = record["patient_prefix"]
        value = (record["split"], record["label"])
        if prefix in expected and expected[prefix] != value:
            raise ValueError("inventory prefix has conflicting split or label")
        expected[prefix] = value
    if not expected:
        raise ValueError("inventory is empty")
    seen, patients = set(), {}
    for row in data:
        required = {"source_prefix", "patient_id", "split", "label", "reviewed"}
        if not isinstance(row, dict) or set(row) != required or row["reviewed"] is not True:
            raise ValueError("each map row must contain exactly the reviewed mapping fields")
        if any(not isinstance(row[k], str) or not row[k].strip() for k in required - {"reviewed"}):
            raise ValueError("map fields must be nonblank strings")
        prefix, patient, split, label = (row[k] for k in ("source_prefix", "patient_id", "split", "label"))
        if prefix in seen:
            raise ValueError("duplicate or conflicting source prefix")
        seen.add(prefix)
        if prefix not in expected or expected[prefix] != (split, label):
            raise ValueError("map differs from inventory split/label or has extra prefix")
        if patient in patients and patients[patient][0] != split:
            raise ValueError("patient leaks across splits")
        if patient in patients and patients[patient][1] != label:
            raise ValueError("patient has conflicting labels")
        patients[patient] = (split, label)
    if seen != set(expected):
        raise ValueError("map missing inventory prefixes")
    return {"rows": len(data), "patients": len(patients), "valid": True}


def download_external(manifest: Path, root: Path) -> list[dict]:
    config = json.loads(manifest.read_text())
    base = root / "data/external/downloads"
    for dataset in config["datasets"]:
        for name in [dataset["name"], *(f["name"] for f in dataset["files"])]:
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
                raise ValueError("unsafe external manifest name")
        for file in dataset["files"]:
            dest = base / dataset["name"] / file["name"]
            for part in (root / "data", root / "data/external", base, dest.parent, dest):
                if part.is_symlink():
                    raise ValueError("symlink in external destination")
    reports = []
    for dataset in config["datasets"]:
        for file in dataset["files"]:
            info = figshare_file(dataset["article_id"], file["id"], dataset["version"])
            if info["computed_md5"] != file["md5"] or info["name"] != file["name"]:
                raise ValueError(f"Figshare manifest mismatch: {dataset['name']} / {file['name']}")
            if file.get("bytes") is not None and info["size"] != file["bytes"]:
                raise ValueError(f"Figshare size mismatch: {dataset['name']} / {file['name']}")
            dest = root / "data/external/downloads" / dataset["name"] / file["name"]
            if dest.exists():
                if digest(dest, "md5") != file["md5"] or (file.get("bytes") is not None and dest.stat().st_size != file["bytes"]):
                    raise ValueError(f"existing file failed integrity check: {dest}")
                state = "verified-existing"
            else:
                atomic_download(info["download_url"], dest, expected={"md5": file["md5"]})
                if file.get("bytes") is not None and dest.stat().st_size != file["bytes"]:
                    dest.unlink(missing_ok=True)
                    raise ValueError(f"download size mismatch: {dataset['name']} / {file['name']}")
                state = "downloaded"
            reports.append({"dataset": dataset["name"], "file": file["name"], "bytes": dest.stat().st_size,
                            "md5": digest(dest, "md5"), "sha256": digest(dest, "sha256"), "status": state})
    return reports


def download_models(root: Path) -> list[dict]:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("install the models extra: uv sync --extra models") from exc
    base = root / "models"
    base.mkdir(parents=True, exist_ok=True)
    inventory = []
    for repo, revision in MODELS.items():
        target = base / repo
        snapshot_download(repo_id=repo, revision=revision, local_dir=target)
        for file in sorted(p for p in target.rglob("*") if p.is_file() and ".cache" not in p.parts):
            inventory.append({"repo": repo, "revision": revision, "path": str(file.relative_to(root)),
                             "bytes": file.stat().st_size, "sha256": digest(file, "sha256")})
    private = ensure_private(root / "data/locked")
    (private / "model-sha256-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    os.chmod(private / "model-sha256-inventory.json", 0o600)
    return inventory
