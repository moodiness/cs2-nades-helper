"""``build`` command: annotation files -> grenades grouped by map -> JSON exports."""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from nades_helper.annotations import ParsedSource, parse_source
from nades_helper.errors import NadesHelperError
from nades_helper.exporters import EXPORTERS
from nades_helper.models import GrenadeKind, MapGrenades, Side, SourceFile
from nades_helper.sources import discover_sources

LOGGER = logging.getLogger(__name__)

# Map pool shipped by CSAFAP; used only to warn when upstream drops a map.
EXPECTED_MAPS = (
    "de_ancient",
    "de_anubis",
    "de_cache",
    "de_dust2",
    "de_inferno",
    "de_mirage",
    "de_nuke",
    "de_overpass",
    "de_train",
    "de_vertigo",
)

SIDE_ORDER = {Side.CT: 0, Side.T: 1, None: 2}


def run_build(input_dir: Path, output_dir: Path, formats: Iterable[str]) -> None:
    started = time.perf_counter()
    grenades = collect_grenades(input_dir)

    for name in formats:
        exporter = EXPORTERS[name](output_dir)
        result = exporter.export(grenades)
        for path in result.written:
            LOGGER.debug("Wrote %s", path)
        for path in result.removed:
            LOGGER.info("Removed legacy export %s", path)
        LOGGER.info(
            "%-13s -> %s (%d written, %d unchanged, %d removed)",
            name,
            exporter.directory,
            len(result.written),
            len(result.unchanged),
            len(result.removed),
        )

    total = sum(len(map_grenades) for map_grenades in grenades.values())
    LOGGER.info(
        "Done in %.2fs: %d maps, %d grenades",
        time.perf_counter() - started,
        len(grenades),
        total,
    )


def collect_grenades(input_dir: Path) -> MapGrenades:
    sources = discover_sources(input_dir)
    if not sources:
        raise NadesHelperError(
            f"No annotation files found in {input_dir} "
            f"(expected layout: {input_dir / 'ancient_CT' / 'ancient_CT.txt'})"
        )
    LOGGER.info("Parsing %d annotation files from %s", len(sources), input_dir)

    parsed: list[ParsedSource] = []
    failures = 0
    for source in sources:
        try:
            result = parse_source(source)
        except NadesHelperError as exc:
            LOGGER.error("%s", exc)
            failures += 1
            continue
        LOGGER.debug("%s -> %s: %d grenades", source.label, result.map_name, len(result.grenades))
        parsed.append(result)

    if failures:
        raise NadesHelperError(
            f"{failures} annotation file(s) could not be parsed; no output was written"
        )

    _log_issues(parsed)
    grenades = group_by_map(parsed)
    _log_maps(grenades, parsed)
    return grenades


def group_by_map(parsed: Iterable[ParsedSource]) -> MapGrenades:
    """Group grenades by map (sorted), CT files first, then T, then side-less files."""
    by_map: defaultdict[str, list[ParsedSource]] = defaultdict(list)
    for result in parsed:
        by_map[result.map_name].append(result)

    grenades: MapGrenades = {}
    for map_name in sorted(by_map):
        results = sorted(by_map[map_name], key=lambda result: _source_order(result.source))
        map_grenades = [grenade for result in results for grenade in result.grenades]
        if map_grenades:
            grenades[map_name] = map_grenades
        else:
            LOGGER.warning("%s: no grenades found, map skipped", map_name)

    return grenades


def _source_order(source: SourceFile) -> tuple[int, str]:
    return SIDE_ORDER[source.side], source.path.name.lower()


def _log_maps(grenades: MapGrenades, parsed: list[ParsedSource]) -> None:
    files_per_map = Counter(result.map_name for result in parsed)
    for map_name, map_grenades in grenades.items():
        kinds = Counter(grenade.kind for grenade in map_grenades)
        breakdown = ", ".join(f"{kind} {kinds[kind]}" for kind in GrenadeKind if kinds[kind])
        LOGGER.info(
            "%-13s %4d grenades from %d file(s)  [%s]",
            map_name,
            len(map_grenades),
            files_per_map[map_name],
            breakdown,
        )

    missing = [map_name for map_name in EXPECTED_MAPS if map_name not in grenades]
    if missing:
        LOGGER.warning("No annotations for expected map(s): %s", ", ".join(missing))


def _log_issues(parsed: list[ParsedSource]) -> None:
    """Details at DEBUG level, one aggregated line per issue kind otherwise."""
    incomplete = 0

    for result in parsed:
        issues, label = result.issues, result.source.label

        for title in issues.unknown_types:
            LOGGER.warning("%s: skipped grenade with unknown type: %s", label, title)
        if issues.incomplete:
            LOGGER.debug(
                "%s: skipped, missing position or aim angles: %s",
                label,
                ", ".join(issues.incomplete),
            )

        incomplete += len(issues.incomplete)

    if incomplete:
        LOGGER.warning(
            "%d lineup(s) skipped: missing position or aim angles (details with --verbose)",
            incomplete,
        )
