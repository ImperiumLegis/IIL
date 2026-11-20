"""Create a disposable, encrypted demo signer and a public trust file."""

import argparse
import base64
import getpass
import json
from pathlib import Path
import sys
import warnings

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="A new directory outside the checkout")
    directory = parser.parse_args().directory.resolve()
    if directory.is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error("Choose a directory outside the repository")
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        parser.error("Use an interactive terminal")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("Choose a disposable demo passphrase: ").encode()
    if not password:
        parser.error("A passphrase is required")
    key = Ed25519PrivateKey.generate()
    encrypted = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.BestAvailableEncryption(password))
    public = base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii")
    trust = {"format_version": "1", "organization": "demo", "reviewers": [{
        "id": "demo-reviewer", "public_key": public, "grants": [
            {"host": "github.example", "provider_id": "1001", "action": "github.file.update"}
        ],
    }]}
    directory.mkdir(mode=0o700)
    (directory / "signer.pem").write_bytes(encrypted)
    (directory / "trust.json").write_text(json.dumps(trust, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
