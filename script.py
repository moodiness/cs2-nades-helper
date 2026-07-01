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
DEFAULT_OUTPUT_FOLDER = "default"
DEFAULT_FILENAME = "nades.json"
HBN_OUTPUT_FOLDER = "hbn"
SECRET_SERVICE_OUTPUT_FOLDER = "secretservice"
SECRET_SERVICE_FILENAME = "grenade_helper.json"
FORMAT_CHOICES = ("all", "default", "hbn", "secretservice")

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

SECRET_SERVICE_GRENADE_NAMES = {
    "he": "hegrenade",
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
    nade_type: str
    type_id: int
    pos: list[Any] | None
    ang: list[Any] | None
    img: str = ""


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
    parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default="all",
        dest="output_format",
        help="Output format. Default: all",
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
                nade_type=grenade_type,
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


def game_map_name(map_name: str) -> str:
    if map_name.startswith(("de_", "cs_", "aim_")):
        return map_name

    return f"de_{map_name}"


class JsonExporter:
    output_folder: str

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def format_output_dir(self) -> Path:
        output_dir = self.output_dir / self.output_folder
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def write_json(self, output_path: Path, payload: dict[str, Any]) -> Path:
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return output_path

    def export(self, grenades_by_map: dict[str, list[Grenade]]) -> list[Path]:
        raise NotImplementedError


class DefaultExporter(JsonExporter):
    output_folder = DEFAULT_OUTPUT_FOLDER

    @staticmethod
    def grenade_to_dict(grenade: Grenade) -> dict[str, Any]:
        payload = {
            "name": grenade.name,
            "desc": grenade.desc,
            "type": grenade.type_id,
        }

        if grenade.pos is not None:
            payload["pos"] = grenade.pos

        if grenade.ang is not None:
            payload["ang"] = grenade.ang

        return payload

    def export(self, grenades_by_map: dict[str, list[Grenade]]) -> list[Path]:
        maps = {
            game_map_name(map_name): [
                self.grenade_to_dict(grenade) for grenade in grenades_by_map[map_name]
            ]
            for map_name in sorted(grenades_by_map, key=map_sort_key)
        }
        payload = {"version": 1, "maps": maps}
        output_path = self.format_output_dir() / DEFAULT_FILENAME

        return [self.write_json(output_path, payload)]


class HbnExporter(JsonExporter):
    output_folder = HBN_OUTPUT_FOLDER

    @staticmethod
    def grenade_to_dict(grenade: Grenade) -> dict[str, Any]:
        payload = {
            "name": grenade.name,
            "desc": grenade.desc,
            "type": grenade.type_id,
            "img": grenade.img,
        }

        if grenade.pos is not None:
            payload["pos"] = grenade.pos

        if grenade.ang is not None:
            payload["ang"] = grenade.ang

        return payload

    def export(self, grenades_by_map: dict[str, list[Grenade]]) -> list[Path]:
        output_dir = self.format_output_dir()
        output_paths: list[Path] = []

        for map_name in sorted(grenades_by_map, key=map_sort_key):
            output_path = output_dir / f"{game_map_name(map_name)}.json"
            payload = {
                "grenades": [
                    self.grenade_to_dict(grenade) for grenade in grenades_by_map[map_name]
                ]
            }
            output_paths.append(self.write_json(output_path, payload))

        return output_paths


class SecretServiceExporter(JsonExporter):
    output_folder = SECRET_SERVICE_OUTPUT_FOLDER

    @staticmethod
    def grenade_to_spot(map_name: str, grenade: Grenade) -> dict[str, Any]:
        spot = {}
        if grenade.ang is not None:
            spot["Angle"] = grenade.ang

        spot["Desc"] = grenade.desc
        spot["MapName"] = map_name
        spot["Nade"] = SECRET_SERVICE_GRENADE_NAMES.get(
            grenade.nade_type, grenade.nade_type
        )
        spot["Name"] = grenade.name

        if grenade.pos is not None:
            spot["Pos"] = grenade.pos

        return spot

    def export(self, grenades_by_map: dict[str, list[Grenade]]) -> list[Path]:
        known_maps = ["<empty>"]
        spots: list[dict[str, Any]] = []

        for map_name in sorted(grenades_by_map, key=map_sort_key):
            formatted_map_name = game_map_name(map_name)
            known_maps.append(formatted_map_name)
            spots.extend(
                self.grenade_to_spot(formatted_map_name, grenade)
                for grenade in grenades_by_map[map_name]
            )

        payload = {"knownMaps": known_maps, "spots": spots}
        output_path = self.format_output_dir() / SECRET_SERVICE_FILENAME

        return [self.write_json(output_path, payload)]


EXPORTERS = {
    "default": DefaultExporter,
    "hbn": HbnExporter,
    "secretservice": SecretServiceExporter,
}


def selected_exporters(output_dir: Path, output_format: str) -> list[JsonExporter]:
    if output_format == "all":
        return [exporter(output_dir) for exporter in EXPORTERS.values()]

    return [EXPORTERS[output_format](output_dir)]


def convert_sources(input_dir: Path, output_dir: Path, output_format: str) -> int:
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
    grenades_by_map: dict[str, list[Grenade]] = {}

    for map_name in sorted(sources_by_map, key=map_sort_key):
        grenades: list[Grenade] = []

        for source in sorted(sources_by_map[map_name], key=source_sort_key):
            parsed_grenades = build_grenades(load_kv3_as_dict(source.path))
            grenades.extend(parsed_grenades)
            LOGGER.info("Parsed %s (%s grenades)", source.path, len(parsed_grenades))

        if not grenades:
            LOGGER.warning("No grenades parsed for %s", map_name)
            continue

        grenades_by_map[map_name] = grenades
        total_maps += 1
        total_grenades += len(grenades)

    for exporter in selected_exporters(output_dir, output_format):
        for output_path in exporter.export(grenades_by_map):
            LOGGER.info("Wrote %s", output_path)

    LOGGER.info("Done: %s maps, %s grenades", total_maps, total_grenades)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    try:
        return convert_sources(args.input_dir, args.output_dir, args.output_format)
    except Exception as exc:
        LOGGER.error("Conversion failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
