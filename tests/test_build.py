from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kv3_builders import aim_node, main_node, write_source

from nades_helper.cli import main


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build(nades: Path, out: Path, *extra: str) -> int:
    return main(["build", "--input-dir", str(nades), "--output-dir", str(out), *extra])


def test_build_writes_every_format(tmp_path: Path) -> None:
    nades, out = tmp_path / "nades", tmp_path / "out"
    write_source(nades, "ancient_T", [main_node("t", "T smoke"), aim_node("t")])
    write_source(nades, "ancient_CT", [main_node("ct", "CT flash", "flash"), aim_node("ct")])
    write_source(
        nades,
        "cache",
        [main_node("he", "Pop", "he", position=(1.5, 2.5, 3.5)), aim_node("he", (-7.0, 8.0, 0.0))],
    )

    assert build(nades, out) == 0

    default = read_json(out / "default" / "nades.json")
    assert list(default["maps"]) == ["de_ancient", "de_cache"]
    assert [g["name"] for g in default["maps"]["de_ancient"]] == ["CT flash", "T smoke"]
    assert default["maps"]["de_cache"] == [
        {
            "name": "Pop",
            "desc": "standing throw",
            "type": 44,
            "pos": [1.5, 2.5, 3.5],
            "ang": [-7.0, 8.0],
        }
    ]

    assert read_json(out / "hbn" / "de_cache.json")["grenades"][0]["img"] == ""

    secret = read_json(out / "secretservice" / "grenade_helper.json")
    assert secret["knownMaps"] == ["<empty>", "de_ancient", "de_cache"]
    assert secret["spots"][-1] == {
        "Angle": [-7.0, 8.0],
        "Desc": "standing throw",
        "MapName": "de_cache",
        "Nade": "hegrenade",
        "Name": "Pop",
        "Pos": [1.5, 2.5, 3.5],
    }

    sensory = read_json(out / "sensory" / "de_cache.json")
    assert (sensory["map"], sensory["version"]) == ("de_cache", 1)
    assert [(lineup["name"], lineup["grenade"]) for lineup in sensory["lineups"]] == [("Pop", "he")]


def test_instant_smoke_packs_are_ignored_and_only_legacy_exports_removed(tmp_path: Path) -> None:
    nades, out = tmp_path / "nades", tmp_path / "out"
    write_source(nades, "anubis_CT", [main_node("m", "CT smoke"), aim_node("m")], "de_anubis")
    write_source(
        nades, "Anubis_Instant_Smoke", [main_node("m", "Instant"), aim_node("m")], "de_anubis"
    )
    for folder in ("hbn", "sensory"):
        (out / folder).mkdir(parents=True)
        (out / folder / "de_anubis_instant_smoke.json").write_text("{}", encoding="utf-8")
        (out / folder / "unrelated.json").write_text("{}", encoding="utf-8")

    assert build(nades, out) == 0

    for folder in ("hbn", "sensory"):
        assert sorted(p.name for p in (out / folder).iterdir()) == [
            "de_anubis.json",
            "unrelated.json",
        ]
    assert [g["name"] for g in read_json(out / "hbn" / "de_anubis.json")["grenades"]] == [
        "CT smoke"
    ]
    secret = read_json(out / "secretservice" / "grenade_helper.json")
    assert secret["knownMaps"] == ["<empty>", "de_anubis"]


def test_build_writes_only_requested_formats(tmp_path: Path) -> None:
    nades, out = tmp_path / "nades", tmp_path / "out"
    write_source(nades, "mirage_T", [main_node("m", "Window"), aim_node("m")])

    assert build(nades, out, "--format", "hbn") == 0

    assert sorted(p.name for p in out.iterdir()) == ["hbn"]


def test_build_writes_nothing_when_a_source_fails_to_parse(tmp_path: Path) -> None:
    nades, out = tmp_path / "nades", tmp_path / "out"
    write_source(nades, "mirage_T", [main_node("m", "Window"), aim_node("m")])
    broken = nades / "nuke_T" / "nuke_T.txt"
    broken.parent.mkdir()
    broken.write_text("{ MapName = ", encoding="utf-8")

    assert build(nades, out) == 1
    assert not out.exists()


def test_build_fails_on_missing_input_dir(tmp_path: Path) -> None:
    assert build(tmp_path / "missing", tmp_path / "out") == 1
