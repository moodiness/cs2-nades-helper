from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from kv3_builders import aim_node, destination_node, main_node, write_source

from nades_helper.annotations import ParsedSource, parse_source
from nades_helper.errors import NadesHelperError
from nades_helper.models import Grenade, GrenadeKind, SourceFile


def parse(root: Path, nodes: list[dict[str, Any]], folder: str = "dust2_CT") -> ParsedSource:
    path = write_source(root, folder, nodes)
    return parse_source(SourceFile(path=path, label=f"{folder}/{folder}.txt", side=None))


def test_lineup_combines_main_node_and_aim_target(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [
            destination_node("a", (100.0, 200.0, 300.0)),
            main_node("a", "Window Smoke", desc="main desc", position=(5.0, 6.0, 7.0)),
            aim_node("a", (-30.0, 10.0, 0.0), desc="", position=(8.0, 9.0, 10.0)),
        ],
    )

    assert result.map_name == "de_dust2"
    assert result.grenades == [
        Grenade(
            name="Window Smoke",
            desc="main desc",
            kind=GrenadeKind.SMOKE,
            pos=[5.0, 6.0, 7.0],
            ang=[-30.0, 10.0],
            source_id="dust2_CT/dust2_CT.txt/a",
            aim_point=[8.0, 9.0, 10.0],
        )
    ]


def test_each_aim_target_of_a_position_is_a_separate_lineup(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [
            main_node("he", "B Short HE", "he"),
            aim_node("he", (11.9, -46.3, 0.0), desc="standing Jumpthrow"),
            destination_node("he"),
            aim_node("he", (-30.2, 3.5, 0.0), desc="standing throw"),
        ],
    )

    assert [(g.ang, g.desc, g.source_id) for g in result.grenades] == [
        ([11.9, -46.3], "standing Jumpthrow", "dust2_CT/dust2_CT.txt/he"),
        ([-30.2, 3.5], "standing throw", "dust2_CT/dust2_CT.txt/he#2"),
    ]


def test_duplicated_main_id_keeps_each_lineup_with_its_own_aim(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [
            main_node("dup", "Wall #1", position=(1.0, 1.0, 1.0)),
            aim_node("dup", (-1.0, -1.0, 0.0)),
            main_node("dup", "Wall #3", position=(3.0, 3.0, 3.0)),
            aim_node("dup", (-3.0, -3.0, 0.0)),
        ],
    )

    assert [(g.name, g.pos, g.ang, g.source_id) for g in result.grenades] == [
        ("Wall #1", [1.0, 1.0, 1.0], [-1.0, -1.0], "dust2_CT/dust2_CT.txt/dup"),
        ("Wall #3", [3.0, 3.0, 3.0], [-3.0, -3.0], "dust2_CT/dust2_CT.txt/dup#2"),
    ]
    assert result.issues.duplicate_ids == ["dup"]


def test_aim_target_declared_before_its_main_node_is_attached(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [aim_node("m", (-5.0, 5.0, 0.0)), aim_node("gone"), main_node("m", "B")],
    )

    assert [g.ang for g in result.grenades] == [[-5.0, 5.0]]
    assert result.issues.orphan_aims == ["gone"]


def test_aim_point_is_optional(tmp_path: Path) -> None:
    result = parse(tmp_path, [main_node("a", "Smoke"), aim_node("a", position=None)])

    assert result.grenades[0].aim_point is None


def test_incomplete_lineups_are_skipped_and_reported(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [
            main_node("ok", "Usable"),
            aim_node("ok"),
            main_node("no-aim", "Missing aim target"),
            main_node("no-pos", "Missing position", position=None),
            aim_node("no-pos"),
            main_node("no-angles", "Missing angles"),
            aim_node("no-angles", angles=None),
        ],
    )

    assert [g.name for g in result.grenades] == ["Usable"]
    assert result.issues.incomplete == [
        "Missing aim target (no-aim)",
        "Missing position (no-pos)",
        "Missing angles (no-angles)",
    ]


def test_jump_throw_comes_from_flag_or_description_not_title(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [
            main_node("flag", "Flagged", jump_throw=True),
            aim_node("flag", desc="standing throw"),
            main_node("desc", "Described"),
            aim_node("desc", desc="standing W-Jumpthrow"),
            main_node("title", "Jump Spot"),
            aim_node("title", desc="standing throw"),
        ],
    )

    assert [(g.name, g.jump_throw) for g in result.grenades] == [
        ("Flagged", True),
        ("Described", True),
        ("Jump Spot", False),
    ]


@pytest.mark.parametrize(
    ("desc", "expected"),
    [
        ("jt", True),
        ("JT", True),
        ("standing W-JumpThrow", True),
        ("jump throw", True),
        ("jump-throw", True),
        ("jump_throw", True),
        ("J.T.", True),
        ("jumping throw", True),
        ("adjust crosshair", False),
        ("jumpthrowing", False),
        ("jump onto the ledge, then throw", False),
    ],
)
def test_jump_throw_spellings_match_whole_words(tmp_path: Path, desc: str, expected: bool) -> None:
    result = parse(tmp_path, [main_node("a", "Smoke"), aim_node("a", desc=desc)])

    assert result.grenades[0].jump_throw is expected


def test_unknown_grenade_type_is_skipped_and_reported(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [
            main_node("decoy", "Decoy", "decoy"),
            aim_node("decoy"),
            main_node("he", "Pop", "HE"),
            aim_node("he"),
        ],
    )

    assert [(g.name, g.kind) for g in result.grenades] == [("Pop", GrenadeKind.HE)]
    assert result.issues.unknown_types == ["Decoy (decoy): GrenadeType='decoy'"]


def test_invalid_kv3_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken" / "broken.txt"
    path.parent.mkdir()
    path.write_text("{ MapName = ", encoding="utf-8")

    with pytest.raises(NadesHelperError, match=r"broken/broken\.txt: invalid KV3"):
        parse_source(SourceFile(path=path, label="broken/broken.txt", side=None))
