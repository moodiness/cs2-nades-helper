from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kv3parser import kv3_to_json


INPUT_DIR = Path("nades")
OUTPUT_DIR = Path("out")

MAP_ORDER = (
    "ancient",
    "anubis",
    "cache",
    "dust2",
    "inferno",
    "mirage",
    "nuke",
    "overpass",
    "train",
    "vertigo",
)

SIDE_ORDER = {"CT": 0, "T": 1, None: 2}

GRENADE_TYPE_IDS = {
    "flash": 43,
    "he": 44,
    "smoke": 45,
    "molotov": 46,
    "incendiary": 46,
}

LOGGER = logging.getLogger("nades-helper")


@dataclass(frozen=True, slots=True)
class SourceFile:
    map_name: str
    side: str | None
    path: Path


@dataclass(frozen=True, slots=True)
class Grenade:
    name: str
    desc: str
    type_id: int
    pos: list[Any] | None
    ang: list[Any] | None
    img: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "desc": self.desc,
            "type": self.type_id,
            "pos": self.pos,
            "ang": self.ang,
            "img": self.img,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert CS2 KV3 grenade annotation files to JSON."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=INPUT_DIR,
        help="Directory containing nade folders. Default: nades",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory where JSON files are written. Default: out",
    )
    return parser.parse_args()


def load_kv3_as_dict(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(kv3_to_json(text))

    if not isinstance(data, dict):
        raise ValueError(f"{path} did not parse to a JSON object")

    return data


def text_value(value: Any) -> str:
    if not isinstance(value, dict):
        return ""

    text = value.get("Text", "")
    return text if isinstance(text, str) else ""


def list_value(value: Any, limit: int | None = None) -> list[Any] | None:
    if not isinstance(value, list):
        return None

    return value[:limit] if limit is not None else value


def build_grenades(data: dict[str, Any]) -> list[Grenade]:
    main_nodes: dict[str, dict[str, Any]] = {}
    aims_by_master: dict[str, list[dict[str, Any]]] = {}

    nodes = (
        value
        for key, value in data.items()
        if key.startswith("MapAnnotationNode") and isinstance(value, dict)
    )

    for node in nodes:
        if node.get("Type") != "grenade":
            continue

        subtype = node.get("SubType")
        if subtype == "main":
            node_id = node.get("Id")
            if not isinstance(node_id, str) or not node_id:
                continue

            main_nodes[node_id] = {
                "name": text_value(node.get("Title")),
                "desc": text_value(node.get("Desc")),
                "position": list_value(node.get("Position")),
                "grenade_type": str(node.get("GrenadeType") or "").lower(),
                "aim_targets": [],
            }
            continue

        if subtype == "aim_target":
            master_id = node.get("MasterNodeId")
            if not isinstance(master_id, str) or not master_id:
                continue

            aims_by_master.setdefault(master_id, []).append(
                {
                    "angles": list_value(node.get("Angles"), limit=2),
                    "desc": text_value(node.get("Desc")),
                }
            )

    for master_id, aims in aims_by_master.items():
        if master_id in main_nodes:
            main_nodes[master_id]["aim_targets"].extend(aims)

    grenades: list[Grenade] = []
    for node in main_nodes.values():
        grenade_type = node["grenade_type"]
        if not grenade_type:
            continue

        aim_targets = node["aim_targets"]
        first_aim = aim_targets[0] if aim_targets else None
        aim_desc = first_aim["desc"] if first_aim else ""

        grenades.append(
            Grenade(
                name=node["name"],
                desc=aim_desc or node["desc"],
                type_id=GRENADE_TYPE_IDS.get(grenade_type, -1),
                pos=node["position"],
                ang=first_aim["angles"] if first_aim else None,
            )
        )

    return grenades


def parse_source_name(name: str) -> tuple[str, str | None]:
    normalized_name = name.lower()

    if normalized_name.endswith("_ct"):
        return normalized_name[:-3], "CT"

    if normalized_name.endswith("_t"):
        return normalized_name[:-2], "T"

    return normalized_name, None


def discover_source_files(input_dir: Path) -> dict[str, list[SourceFile]]:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    sources_by_map: dict[str, list[SourceFile]] = {}

    for folder in sorted(input_dir.iterdir(), key=lambda path: path.name.lower()):
        if not folder.is_dir():
            continue

        text_files = sorted(folder.glob("*.txt"), key=lambda path: path.name.lower())
        expected_name = f"{folder.name}.txt".lower()
        matching_files = [path for path in text_files if path.name.lower() == expected_name]
        source_files = matching_files or text_files

        for source_path in source_files:
            map_name, side = parse_source_name(source_path.stem)
            source = SourceFile(map_name=map_name, side=side, path=source_path)
            sources_by_map.setdefault(map_name, []).append(source)

    return sources_by_map


def map_sort_key(map_name: str) -> tuple[int, str]:
    try:
        return MAP_ORDER.index(map_name), map_name
    except ValueError:
        return len(MAP_ORDER), map_name


def source_sort_key(source: SourceFile) -> tuple[int, str]:
    return SIDE_ORDER[source.side], source.path.name.lower()


def write_map_output(output_dir: Path, map_name: str, grenades: list[dict[str, Any]]) -> Path:
    output_path = output_dir / f"de_{map_name}.json"
    payload = {"grenades": grenades}

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return output_path


def convert_sources(input_dir: Path, output_dir: Path) -> int:
    sources_by_map = discover_source_files(input_dir)
    if not sources_by_map:
        LOGGER.error("No source files found in %s", input_dir)
        LOGGER.error("Expected layout example: nades/ancient_CT/ancient_CT.txt")
        return 1

    missing_maps = [map_name for map_name in MAP_ORDER if map_name not in sources_by_map]
    if missing_maps:
        LOGGER.warning("Missing source folders for: %s", ", ".join(missing_maps))

    output_dir.mkdir(parents=True, exist_ok=True)

    total_maps = 0
    total_grenades = 0

    for map_name in sorted(sources_by_map, key=map_sort_key):
        grenades: list[dict[str, Any]] = []

        for source in sorted(sources_by_map[map_name], key=source_sort_key):
            parsed_grenades = build_grenades(load_kv3_as_dict(source.path))
            grenades.extend(grenade.to_dict() for grenade in parsed_grenades)
            LOGGER.info("Parsed %s (%s grenades)", source.path, len(parsed_grenades))

        if not grenades:
            LOGGER.warning("No grenades parsed for %s", map_name)
            continue

        output_path = write_map_output(output_dir, map_name, grenades)
        total_maps += 1
        total_grenades += len(grenades)
        LOGGER.info("Wrote %s (%s total grenades)", output_path, len(grenades))

    LOGGER.info("Done: %s maps, %s grenades", total_maps, total_grenades)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    try:
        return convert_sources(args.input_dir, args.output_dir)
    except Exception as exc:
        LOGGER.error("Conversion failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
