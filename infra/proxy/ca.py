"""Create a host-only mitmproxy CA and a separately mountable public bundle.

Run once per installation: python -m infra.proxy.ca PRIVATE_DIR PUBLIC_DIR
Never mount PRIVATE_DIR in an agent. PUBLIC_DIR can be mounted read-only.
"""
import argparse
import os
from pathlib import Path
import subprocess


def generate(private_dir: Path, public_dir: Path) -> None:
    private_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(private_dir, 0o700)
    public_dir.mkdir(mode=0o755, parents=True, exist_ok=False)
    key = private_dir / "key.pem"
    cert = public_dir / "ca.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:4096", "-sha256",
                    "-nodes", "-days", "3650", "-subj", "/CN=WSP local proxy CA",
                    "-addext", "basicConstraints=critical,CA:TRUE",
                    "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                    "-keyout", str(key), "-out", str(cert)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   preexec_fn=lambda: os.umask(0o077))
    os.chmod(key, 0o600)
    combined = private_dir / "mitmproxy-ca.pem"
    combined.write_bytes(key.read_bytes() + cert.read_bytes())
    os.chmod(combined, 0o600)
    key.unlink()
    bundle = public_dir / "bundle.pem"
    bundle.write_bytes(Path("/etc/ssl/certs/ca-certificates.crt").read_bytes() + b"\n" + cert.read_bytes())
    os.chmod(cert, 0o644)
    os.chmod(bundle, 0o644)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_dir", type=Path)
    parser.add_argument("public_dir", type=Path)
    args = parser.parse_args()
    generate(args.private_dir, args.public_dir)
