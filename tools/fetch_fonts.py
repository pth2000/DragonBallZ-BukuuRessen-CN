#!/usr/bin/env python3
"""Fetch and verify the exact font assets used by the release build."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from _bootstrap import PROJECT_ROOT

ARK_REPOSITORY = "https://github.com/TakWolf/ark-pixel-font.git"
ARK_COMMIT = "417febb32c2d84d326e8f9f8f289da2122461a00"
FUSION_VERSION = "2026.07.20"
FUSION_ARCHIVE = f"fusion-pixel-font-12px-monospaced-bdf-v{FUSION_VERSION}.zip"
FUSION_URL = (
    "https://github.com/TakWolf/fusion-pixel-font/releases/download/"
    f"{FUSION_VERSION}/{FUSION_ARCHIVE}"
)
FUSION_ARCHIVE_SHA256 = "aea98326638e138de8583f0ae87db9eb722b9f44519361a32e0ee9577b3c6586"
FUSION_BDF_SHA256 = "8e4a12e821efad608bcb464d685ce50c70693f85a1e95dead9575e6cecafffc7"
ZHENGGE_VERSION = "v1.0.0"
ZHENGGE_TTF_URL = (
    "https://github.com/yzdnn/ZhengGeDianHei-16/releases/download/"
    f"{ZHENGGE_VERSION}/ZhengGeDianHei-16.ttf"
)
ZHENGGE_OFL_URL = (
    "https://raw.githubusercontent.com/yzdnn/ZhengGeDianHei-16/"
    f"{ZHENGGE_VERSION}/OFL.txt"
)
ZHENGGE_TTF_SHA256 = "ca9d5d362b589ef2743c500b3099bd09b11e63058b8f29d374f1f7e3e59d606c"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "dbzbr-cn-build/1.0"})
    with urllib.request.urlopen(request) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def checked_download(url: str, destination: Path, expected_sha256: str) -> None:
    if destination.is_file() and sha256(destination) == expected_sha256:
        return
    if destination.exists():
        raise RuntimeError(f"existing file has the wrong SHA-256: {destination}")
    print(f"download: {url}")
    download(url, destination)
    actual = sha256(destination)
    if actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            f"download SHA-256 mismatch for {destination.name}\n"
            f"expected: {expected_sha256}\nactual:   {actual}"
        )


def prepare_ark(vendor_root: Path) -> Path:
    destination = vendor_root / "ark-pixel-font"
    if destination.exists():
        if not (destination / ".git").is_dir():
            raise RuntimeError(f"Ark destination exists but is not a Git clone: {destination}")
    else:
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", ARK_REPOSITORY, str(destination)],
            check=True,
        )
    safe_directory = destination.resolve().as_posix()
    current_head = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={safe_directory}",
            "-C",
            str(destination),
            "rev-parse",
            "HEAD",
        ],
        text=True,
    ).strip()
    if current_head == ARK_COMMIT:
        return destination
    subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={safe_directory}",
            "-C",
            str(destination),
            "fetch",
            "--depth=1",
            "origin",
            ARK_COMMIT,
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={safe_directory}",
            "-C",
            str(destination),
            "checkout",
            "--detach",
            ARK_COMMIT,
        ],
        check=True,
    )
    head = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={safe_directory}",
            "-C",
            str(destination),
            "rev-parse",
            "HEAD",
        ],
        text=True,
    ).strip()
    if head != ARK_COMMIT:
        raise RuntimeError(f"Ark commit mismatch: {head}")
    return destination


def prepare_fusion(vendor_root: Path) -> Path:
    destination = vendor_root / "fusion-pixel-font" / f"12px-monospaced-bdf-v{FUSION_VERSION}"
    bdf = destination / "fusion-pixel-12px-monospaced-zh_hans.bdf"
    if bdf.is_file() and sha256(bdf) == FUSION_BDF_SHA256:
        return bdf
    if destination.exists():
        raise RuntimeError(f"Fusion destination exists but is incomplete or modified: {destination}")

    with tempfile.TemporaryDirectory() as directory:
        archive_path = Path(directory) / FUSION_ARCHIVE
        checked_download(FUSION_URL, archive_path, FUSION_ARCHIVE_SHA256)
        extract_root = Path(directory) / "extract"
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                member_path = (extract_root / member.filename).resolve()
                if extract_root.resolve() not in member_path.parents and member_path != extract_root.resolve():
                    raise RuntimeError(f"unsafe ZIP path: {member.filename}")
            archive.extractall(extract_root)
        candidates = list(extract_root.rglob("fusion-pixel-12px-monospaced-zh_hans.bdf"))
        if len(candidates) != 1:
            raise RuntimeError("Fusion archive does not contain exactly one zh_hans BDF")
        source_dir = candidates[0].parent
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, destination)

    if sha256(bdf) != FUSION_BDF_SHA256:
        raise RuntimeError("extracted Fusion BDF has the wrong SHA-256")
    return bdf


def prepare_zhengge(vendor_root: Path) -> Path:
    destination = vendor_root / "zhengge-dianhei-16"
    ttf = destination / "ZhengGeDianHei-16.ttf"
    ofl = destination / "OFL.txt"
    checked_download(ZHENGGE_TTF_URL, ttf, ZHENGGE_TTF_SHA256)
    if not ofl.exists():
        print(f"download: {ZHENGGE_OFL_URL}")
        download(ZHENGGE_OFL_URL, ofl)
    return ttf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vendor-dir",
        type=Path,
        default=PROJECT_ROOT / "work/vendor",
        help="Local ignored dependency directory",
    )
    args = parser.parse_args()
    args.vendor_dir.mkdir(parents=True, exist_ok=True)

    ark = prepare_ark(args.vendor_dir)
    fusion = prepare_fusion(args.vendor_dir)
    zhengge = prepare_zhengge(args.vendor_dir)
    print("font assets ready")
    print(f"  Ark:      {ark}")
    print(f"  Fusion:   {fusion}")
    print(f"  ZhengGe:  {zhengge}")


if __name__ == "__main__":
    main()
