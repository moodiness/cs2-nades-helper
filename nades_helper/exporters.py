"""JSON output formats. Each exporter owns one sub-folder of the output directory."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
from uuid import NAMESPACE_URL, uuid5

from nades_helper.models import Grenade, GrenadeKind, MapGrenades
from nades_helper.throws import throw_settings

Payload = dict[str, Any]

# CS weapon definition indexes used by the default and HBN formats.
WEAPON_IDS = {
    GrenadeKind.FLASH: 43,
    GrenadeKind.HE: 44,
    GrenadeKind.SMOKE: 45,
    GrenadeKind.MOLOTOV: 46,
    GrenadeKind.INCENDIARY: 46,
}

SECRET_SERVICE_NADE_NAMES = {
    GrenadeKind.HE: "hegrenade",
}

SENSORY_GRENADE_NAMES = {
    GrenadeKind.SMOKE: "smoke",
    GrenadeKind.FLASH: "flash",
    GrenadeKind.MOLOTOV: "fire",
    GrenadeKind.INCENDIARY: "fire",
    GrenadeKind.HE: "he",
}

# Per-map files once produced for instant smoke packs, which are now ignored.
LEGACY_INSTANT_SMOKE_FILES = "*_instant_smoke.json"


@dataclass(slots=True)
class ExportResult:
    written: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)


class Exporter(ABC):
    name: ClassVar[str]
    legacy_files: ClassVar[tuple[str, ...]] = ()
    """Glob patterns of obsolete files this format used to write; deleted on export."""

    def __init__(self, output_dir: Path) -> None:
        self.directory = output_dir / self.name

    @abstractmethod
    def render(self, grenades: MapGrenades) -> dict[str, Payload]:
        """Return the files of this format as ``{file name: JSON payload}``."""

    def export(self, grenades: MapGrenades) -> ExportResult:
        documents = self.render(grenades)
        result = ExportResult()
        self.directory.mkdir(parents=True, exist_ok=True)

        for filename, payload in documents.items():
            path = self.directory / filename
            if write_json(path, payload):
                result.written.append(path)
            else:
                result.unchanged.append(path)

        for pattern in self.legacy_files:
            for legacy in sorted(self.directory.glob(pattern)):
                if legacy.name not in documents and legacy.is_file():
                    legacy.unlink()
                    result.removed.append(legacy)

        return result


class DefaultExporter(Exporter):
    """``default/nades.json``: every map in one file."""

    name = "default"

    def render(self, grenades: MapGrenades) -> dict[str, Payload]:
        maps = {
            map_name: [_weapon_id_entry(grenade) for grenade in map_grenades]
            for map_name, map_grenades in grenades.items()
        }
        return {"nades.json": {"version": 1, "maps": maps}}


class HbnExporter(Exporter):
    """``hbn/<map>.json``: one file per map."""

    name = "hbn"
    legacy_files = (LEGACY_INSTANT_SMOKE_FILES,)

    def render(self, grenades: MapGrenades) -> dict[str, Payload]:
        return {
            f"{map_name}.json": {
                "grenades": [_weapon_id_entry(grenade, img="") for grenade in map_grenades]
            }
            for map_name, map_grenades in grenades.items()
        }


class SecretServiceExporter(Exporter):
    """``secretservice/grenade_helper.json``: flat spot list for the SecretService helper."""

    name = "secretservice"

    def render(self, grenades: MapGrenades) -> dict[str, Payload]:
        spots = [
            {
                "Angle": grenade.ang,
                "Desc": grenade.desc,
                "MapName": map_name,
                "Nade": SECRET_SERVICE_NADE_NAMES.get(grenade.kind, grenade.kind.value),
                "Name": grenade.name,
                "Pos": grenade.pos,
            }
            for map_name, map_grenades in grenades.items()
            for grenade in map_grenades
        ]
        return {"grenade_helper.json": {"knownMaps": ["<empty>", *grenades], "spots": spots}}


class SensoryExporter(Exporter):
    """``sensory/<map>.json``: manual-mode lineups for Sensory."""

    name = "sensory"
    legacy_files = (LEGACY_INSTANT_SMOKE_FILES,)

    def render(self, grenades: MapGrenades) -> dict[str, Payload]:
        return {
            f"{map_name}.json": {
                "lineups": [_sensory_lineup(map_name, grenade) for grenade in map_grenades],
                "map": map_name,
                "version": 1,
            }
            for map_name, map_grenades in grenades.items()
        }


EXPORTERS: dict[str, type[Exporter]] = {
    exporter.name: exporter
    for exporter in (DefaultExporter, HbnExporter, SecretServiceExporter, SensoryExporter)
}


def write_json(path: Path, payload: Payload) -> bool:
    """Atomically write ``payload``; return False when the file already had this content."""
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    try:
        if path.read_bytes() == data:
            return False
    except FileNotFoundError:
        pass

    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)
    return True


def _weapon_id_entry(grenade: Grenade, **extra: Any) -> Payload:
    return {
        "name": grenade.name,
        "desc": grenade.desc,
        "type": WEAPON_IDS[grenade.kind],
        **extra,
        "pos": grenade.pos,
        "ang": grenade.ang,
    }


def _sensory_lineup(map_name: str, grenade: Grenade) -> Payload:
    # Fixed manual-mode settings; see the README for the rationale behind each value.
    stance, throw = throw_settings(grenade.desc)
    lineup: Payload = {
        "angle_tolerance": 0.11999999731779099,
        "grenade": SENSORY_GRENADE_NAMES[grenade.kind],
        "id": uuid5(NAMESPACE_URL, f"cs2-nades-helper/{map_name}/{grenade.source_id}").hex,
        "jump_throw": grenade.jump_throw,
        "landing_tolerance": 24.0,
        "manual_action": True,
        "max_speed": 8.0,
        "movement": "stationary",
        "name": grenade.name,
        "notes": grenade.desc,
        "origin": grenade.pos,
        "position_tolerance": 4.0,
        "stance": stance,
        "throw": throw,
        "vertical_tolerance": 3.0,
        "view_angle": grenade.ang,
    }
    if grenade.aim_point is not None:
        lineup["aim_point"] = grenade.aim_point
    return lineup
