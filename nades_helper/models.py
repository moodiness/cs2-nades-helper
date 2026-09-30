from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Side(StrEnum):
    CT = "CT"
    T = "T"


class GrenadeKind(StrEnum):
    """Grenade kinds, declared in display order."""

    SMOKE = "smoke"
    FLASH = "flash"
    MOLOTOV = "molotov"
    INCENDIARY = "incendiary"
    HE = "he"

    @classmethod
    def parse(cls, raw: str) -> GrenadeKind | None:
        try:
            return cls(raw.strip().lower())
        except ValueError:
            return None


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: Path
    label: str
    """Path relative to the input folder (``dust2_CT/dust2_CT.txt``), used in logs and ids."""
    side: Side | None


@dataclass(frozen=True, slots=True)
class Grenade:
    """One throwable lineup: a standing position plus one aim target."""

    name: str
    desc: str
    kind: GrenadeKind
    pos: list[float]
    ang: list[float]
    source_id: str
    """``<source label>/<main node Id>``, suffixed ``#2``, ``#3``... for further aim targets
    of the same node. Stable across runs, reordering and text edits."""
    jump_throw: bool = False
    aim_point: list[float] | None = None


# Game map name (e.g. "de_mirage") -> grenades, in export order.
MapGrenades = dict[str, list[Grenade]]
