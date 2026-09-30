"""``update`` command: download the CSAFAP annotation files into the nades folder."""

from __future__ import annotations

import http.client
import logging
import os
import shutil
import tempfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from nades_helper import __version__
from nades_helper.errors import NadesHelperError

LOGGER = logging.getLogger(__name__)

DEFAULT_ARCHIVE_URL = (
    "https://github.com/FNScence/CSAFAP-config-package/archive/refs/heads/main.zip"
)
DEFAULT_SOURCE_PATH = "csafap/csgo/annotations/local"
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True, slots=True)
class TreeChanges:
    added: list[str]
    removed: list[str]
    changed: list[str]

    def __bool__(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def run_update(
    destination: Path,
    url: str = DEFAULT_ARCHIVE_URL,
    source_path: str = DEFAULT_SOURCE_PATH,
    timeout: float = DEFAULT_TIMEOUT,
) -> TreeChanges:
    """Replace ``destination`` with ``source_path`` from the GitHub archive at ``url``.

    The archive is downloaded and extracted next to ``destination`` first, so a failed
    download or a malformed archive never leaves a half-updated folder behind.
    """
    parent = destination.absolute().parent
    parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".nades-update-", dir=parent) as work:
        work_dir = Path(work)
        archive = work_dir / "source.zip"
        staging = work_dir / "nades"

        download(url, archive, timeout)
        file_count = extract_subtree(archive, source_path, staging)
        LOGGER.info("Extracted %d files from %s", file_count, source_path)

        changes = diff_trees(destination, staging)
        if not changes:
            LOGGER.info("%s is already up to date", destination)
            return changes

        for label, paths in (
            ("added", changes.added),
            ("removed", changes.removed),
            ("changed", changes.changed),
        ):
            for path in paths:
                LOGGER.debug("%s: %s", label, path)

        replace_directory(destination, staging, backup=work_dir / "previous")

    LOGGER.info(
        "Updated %s: %d changed, %d added, %d removed",
        destination,
        len(changes.changed),
        len(changes.added),
        len(changes.removed),
    )
    return changes


def download(url: str, target: Path, timeout: float) -> None:
    LOGGER.info("Downloading %s", url)
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": f"nades-helper/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, target.open("wb") as out:
            shutil.copyfileobj(response, out)
    except (OSError, http.client.HTTPException) as exc:
        raise NadesHelperError(f"Download failed: {url}: {exc}") from exc

    size_mib = target.stat().st_size / (1024 * 1024)
    LOGGER.info("Downloaded %.1f MiB in %.1fs", size_mib, time.perf_counter() - started)


def extract_subtree(archive: Path, source_path: str, staging: Path) -> int:
    """Extract ``source_path`` (relative to the archive's root folder) into ``staging``."""
    prefix = PurePosixPath(source_path.strip("/"))
    count = 0

    try:
        with zipfile.ZipFile(archive) as zip_file:
            for info in zip_file.infolist():
                if info.is_dir():
                    continue

                # GitHub archives wrap everything in a "<repo>-<branch>/" folder.
                parts = PurePosixPath(info.filename).parts
                if len(parts) < 2:
                    continue
                try:
                    relative = PurePosixPath(*parts[1:]).relative_to(prefix)
                except ValueError:
                    continue
                if ".." in relative.parts:
                    raise NadesHelperError(f"Unsafe path in archive: {info.filename}")

                target = staging.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zip_file.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
    except zipfile.BadZipFile as exc:
        raise NadesHelperError(f"Downloaded file is not a valid zip archive: {exc}") from exc

    if not any(staging.rglob("*.txt")):
        raise NadesHelperError(f"No annotation files found under '{source_path}' in the archive")

    return count


def diff_trees(old: Path, new: Path) -> TreeChanges:
    old_files = _relative_files(old)
    new_files = _relative_files(new)
    common = old_files.keys() & new_files.keys()
    return TreeChanges(
        added=sorted(new_files.keys() - old_files.keys()),
        removed=sorted(old_files.keys() - new_files.keys()),
        changed=sorted(
            name for name in common if old_files[name].read_bytes() != new_files[name].read_bytes()
        ),
    )


def replace_directory(destination: Path, replacement: Path, backup: Path) -> None:
    try:
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(replacement, destination)
        except OSError:
            if backup.exists():
                os.replace(backup, destination)
            raise
    except OSError as exc:
        raise NadesHelperError(f"Cannot replace {destination}: {exc}") from exc


def _relative_files(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {path.relative_to(root).as_posix(): path for path in root.rglob("*") if path.is_file()}
