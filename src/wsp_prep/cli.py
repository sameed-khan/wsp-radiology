from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import requests

from .core import (download_external, download_models, fetch_mfxr, inventory_archive,
                   validate_patient_map)


def doctor(root: Path) -> dict:
    try:
        import torch
        gpu = {"torch": torch.__version__, "cuda_available": torch.cuda.is_available(),
               "device_count": torch.cuda.device_count()}
    except ImportError:
        gpu = {"torch": "not-installed", "cuda_available": False, "device_count": 0}
    try:
        from huggingface_hub import get_token
        hf_auth = "available" if get_token() else "unavailable"
    except ImportError:
        hf_auth = "hub-library-not-installed"
    disk = shutil.disk_usage(root)
    try:
        response = requests.get("https://stanford.redivis.com/datasets/cv1a-apytk3j44", timeout=15,
                                allow_redirects=True)
        mura = {"http_status": response.status_code,
                "access": "public_page_reachable_no_license_acceptance_attempted" if response.ok else "blocked_or_unavailable"}
    except requests.RequestException as exc:
        mura = {"access": "unavailable", "error_type": type(exc).__name__}
    return {"gpu": gpu, "huggingface_credentials": hf_auth,
            "figshare_network": "not-probed", "mura": mura,
            "disk_free_bytes": disk.free, "data_root_exists": (root / "data").exists()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wsp-prep")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download")
    prep = sub.add_parser("prepare")
    prep.add_argument("--archive", type=Path)
    prep.add_argument("--rebuild", action="store_true")
    check = sub.add_parser("validate-map")
    check.add_argument("map", type=Path)
    check.add_argument("--inventory", type=Path, required=True)
    external = sub.add_parser("download-external")
    external.add_argument("--manifest", type=Path, default=Path("config/public-datasets.json"))
    sub.add_parser("models")
    sub.add_parser("doctor")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "download":
            result = {"archive": str(fetch_mfxr(root)), "status": "verified"}
        elif args.command == "prepare":
            archive = (args.archive or root / "data/locked/downloads/MFXR.zip").resolve()
            result = inventory_archive(archive, root, rebuild=args.rebuild)
        elif args.command == "validate-map":
            result = validate_patient_map(args.map, args.inventory)
        elif args.command == "download-external":
            manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
            result = download_external(manifest, root)
        elif args.command == "models":
            result = download_models(root)
        else:
            result = doctor(root)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        if isinstance(exc, requests.RequestException):
            status = getattr(getattr(exc, "response", None), "status_code", None)
            print(f"error: {type(exc).__name__}; HTTP status: {status}; network request failed", file=sys.stderr)
        else:
            import re
            message = re.sub(r"https?://[^\s]+", "[redacted URL]", str(exc))
            print(f"error: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
