"""Helpers writing small CS2 annotation files for tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

KV3_HEADER = (
    "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
    "format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->"
)

Vector = Sequence[float] | None


def main_node(
    node_id: str,
    title: str,
    grenade_type: str = "smoke",
    *,
    desc: str = "",
    position: Vector = (1.0, 2.0, 3.0),
    jump_throw: bool = False,
    enabled: bool = True,
) -> dict[str, Any]:
    return {
        "Enabled": enabled,
        "Type": "grenade",
        "Id": node_id,
        "SubType": "main",
        "Position": position,
        "Title": {"Text": title},
        "Desc": {"Text": desc},
        "JumpThrow": jump_throw,
        "GrenadeType": grenade_type,
    }


def aim_node(
    master_id: str,
    angles: Vector = (-10.0, 20.0, 0.0),
    desc: str = "standing throw",
    *,
    position: Vector = (10.0, 20.0, 30.0),
) -> dict[str, Any]:
    return {
        "Enabled": True,
        "Type": "grenade",
        "SubType": "aim_target",
        "Position": position,
        "Angles": angles,
        "Desc": {"Text": desc},
        "MasterNodeId": master_id,
    }


def destination_node(master_id: str, position: Vector = (100.0, 200.0, 300.0)) -> dict[str, Any]:
    return {
        "Enabled": True,
        "Type": "grenade",
        "SubType": "destination",
        "Position": position,
        "MasterNodeId": master_id,
    }


def render_kv3(nodes: Sequence[dict[str, Any]], map_name: str = "de_test") -> str:
    lines = [KV3_HEADER, "{", f'\tMapName = "{map_name}"']
    for index, node in enumerate(nodes, start=1):
        lines.append(f"\tMapAnnotationNode{index} = ")
        lines.extend(_render_object(node, depth=1))
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_source(
    root: Path, folder: str, nodes: Sequence[dict[str, Any]] = (), map_name: str = "de_test"
) -> Path:
    """Write ``<root>/<folder>/<folder>.txt`` and return its path."""
    path = root / folder / f"{folder}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_kv3(nodes, map_name), encoding="utf-8")
    return path


def _render_object(values: dict[str, Any], depth: int) -> list[str]:
    indent = "\t" * depth
    lines = [f"{indent}{{"]
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{indent}\t{key} = ")
            lines.extend(_render_object(value, depth + 1))
        else:
            lines.append(f"{indent}\t{key} = {_render_value(value)}")
    lines.append(f"{indent}}}")
    return lines


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list | tuple):
        return "[ " + ", ".join(_render_value(item) for item in value) + " ]"
    return repr(value)
