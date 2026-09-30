"""Parsing of CS2 map annotation files (KV3) into grenade lineups."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kv3parser import KV3ParseError, KV3Parser

from nades_helper.errors import NadesHelperError
from nades_helper.models import Grenade, GrenadeKind, SourceFile
from nades_helper.sources import map_name_for
from nades_helper.throws import is_jump_throw

NODE_KEY_PREFIX = "MapAnnotationNode"
UNTITLED = "<untitled>"


@dataclass(slots=True)
class SourceIssues:
    """Data-quality problems found in one annotation file."""

    incomplete: list[str] = field(default_factory=list)
    unknown_types: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ParsedSource:
    source: SourceFile
    map_name: str
    grenades: list[Grenade]
    issues: SourceIssues


@dataclass(frozen=True, slots=True)
class _Aim:
    angles: list[float] | None
    position: list[float] | None
    desc: str


@dataclass(slots=True)
class _Lineup:
    node_id: str
    name: str
    desc: str
    grenade_type: str
    pos: list[float] | None
    jump_throw: bool
    aims: list[_Aim] = field(default_factory=list)


def parse_source(source: SourceFile) -> ParsedSource:
    grenades, issues = extract_grenades(load_document(source), source.label)
    return ParsedSource(
        source=source, map_name=map_name_for(source), grenades=grenades, issues=issues
    )


def load_document(source: SourceFile) -> dict[str, Any]:
    try:
        text = source.path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise NadesHelperError(f"{source.label}: cannot read file: {exc}") from exc

    try:
        document = KV3Parser(text).parse()
    except KV3ParseError as exc:
        raise NadesHelperError(f"{source.label}: invalid KV3: {exc}") from exc

    if not isinstance(document, dict):
        raise NadesHelperError(f"{source.label}: root KV3 value is not an object")

    return document


def extract_grenades(
    document: dict[str, Any], source_label: str
) -> tuple[list[Grenade], SourceIssues]:
    """Build one grenade per (main node, aim target) pair, in file order.

    Aim targets reference their main node through ``MasterNodeId``; a position with several
    aim targets yields several lineups. Lineups without a position or aim angles are skipped:
    no coordinates are invented.
    """
    issues = SourceIssues()
    lineups: dict[str, _Lineup] = {}
    aims_by_master: dict[str, list[_Aim]] = {}

    for key, node in document.items():
        if not key.startswith(NODE_KEY_PREFIX) or not isinstance(node, dict):
            continue
        if node.get("Type") != "grenade":
            continue

        subtype = node.get("SubType")
        if subtype == "main":
            node_id = _string(node.get("Id"))
            if not node_id:
                continue
            lineups[node_id] = _Lineup(
                node_id=node_id,
                name=_text(node.get("Title")),
                desc=_text(node.get("Desc")),
                grenade_type=_string(node.get("GrenadeType")),
                pos=_vector(node.get("Position"), 3),
                jump_throw=node.get("JumpThrow") is True,
            )

        elif subtype == "aim_target":
            master_id = _string(node.get("MasterNodeId"))
            if not master_id:
                continue
            aims_by_master.setdefault(master_id, []).append(
                _Aim(
                    angles=_vector(node.get("Angles"), 2),
                    position=_vector(node.get("Position"), 3),
                    desc=_text(node.get("Desc")),
                )
            )

    for master_id, aims in aims_by_master.items():
        if master_id in lineups:
            lineups[master_id].aims.extend(aims)

    grenades: list[Grenade] = []
    used_ids: set[str] = set()
    for lineup in lineups.values():
        title = f"{lineup.name or UNTITLED} ({lineup.node_id})"
        kind = GrenadeKind.parse(lineup.grenade_type)
        if kind is None:
            issues.unknown_types.append(f"{title}: GrenadeType={lineup.grenade_type!r}")
            continue

        if lineup.pos is None or not lineup.aims:
            issues.incomplete.append(title)
            continue

        for aim in lineup.aims:
            if aim.angles is None:
                issues.incomplete.append(title)
                continue

            desc = aim.desc or lineup.desc
            grenades.append(
                Grenade(
                    name=lineup.name,
                    desc=desc,
                    kind=kind,
                    pos=lineup.pos,
                    ang=aim.angles,
                    source_id=_unique_id(f"{source_label}/{lineup.node_id}", used_ids),
                    jump_throw=lineup.jump_throw or is_jump_throw(desc),
                    aim_point=aim.position,
                )
            )

    return grenades, issues


def _unique_id(base: str, used: set[str]) -> str:
    """``base`` for the first lineup of a node, then ``base#2``, ``base#3``..."""
    candidate, index = base, 1
    while candidate in used:
        index += 1
        candidate = f"{base}#{index}"
    used.add(candidate)
    return candidate


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text(value: Any) -> str:
    """Read the ``Text`` field of a KV3 label object such as ``Title`` or ``Desc``."""
    if not isinstance(value, dict):
        return ""
    text = value.get("Text")
    return text if isinstance(text, str) else ""


def _vector(value: Any, size: int) -> list[float] | None:
    """First ``size`` numbers of a KV3 array, or None when it is missing or too short."""
    if not isinstance(value, list) or len(value) < size:
        return None
    if not all(isinstance(item, int | float) and not isinstance(item, bool) for item in value):
        return None
    return value[:size]
