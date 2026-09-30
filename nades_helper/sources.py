"""Discovery of annotation files inside the nades folder."""

from __future__ import annotations

import logging
from pathlib import Path

from nades_helper.errors import NadesHelperError
from nades_helper.models import Side, SourceFile

LOGGER = logging.getLogger(__name__)

SIDE_SUFFIXES = (("_ct", Side.CT), ("_t", Side.T))
GAME_MAP_PREFIXES = ("de_", "cs_", "ar_", "aim_")

# CSAFAP also ships per-map instant smoke packs whose lineups already exist in the map folders.
IGNORED_FOLDER_SUFFIX = "_instant_smoke"


def parse_side(stem: str) -> tuple[str, Side | None]:
    """Split ``ancient_CT`` into ``("ancient", Side.CT)``; unknown suffixes have no side."""
    lowered = stem.lower()
    for suffix, side in SIDE_SUFFIXES:
        if lowered.endswith(suffix):
            return lowered.removesuffix(suffix), side
    return lowered, None


def map_name_for(source: SourceFile) -> str:
    """Game map name derived from the file name: ``ancient_CT.txt`` -> ``de_ancient``."""
    base, _ = parse_side(source.path.stem)
    return base if base.startswith(GAME_MAP_PREFIXES) else f"de_{base}"


def discover_sources(input_dir: Path) -> list[SourceFile]:
    """Return one annotation file per sub-folder (``<folder>/<folder>.txt``).

    Folders without a file named after them contribute every ``.txt`` file they contain.
    Instant smoke packs are skipped.
    """
    if not input_dir.is_dir():
        raise NadesHelperError(f"Input directory not found: {input_dir}")

    sources: list[SourceFile] = []
    folders = sorted((p for p in input_dir.iterdir() if p.is_dir()), key=lambda p: p.name.lower())

    for folder in folders:
        if folder.name.lower().endswith(IGNORED_FOLDER_SUFFIX):
            LOGGER.debug("Ignoring instant smoke pack %s", folder.name)
            continue

        text_files = sorted(folder.glob("*.txt"), key=lambda p: p.name.lower())
        preferred = [p for p in text_files if p.stem.lower() == folder.name.lower()]
        selected = preferred or text_files

        if not selected:
            LOGGER.debug("Skipping %s: no .txt file", folder)
            continue

        for path in selected:
            _, side = parse_side(path.stem)
            label = path.relative_to(input_dir).as_posix()
            sources.append(SourceFile(path=path, label=label, side=side))

    return sources
