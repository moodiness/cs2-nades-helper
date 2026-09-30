from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from nades_helper.exporters import SensoryExporter
from nades_helper.models import Grenade, GrenadeKind


def grenade(name: str = "Smoke", desc: str = "standing throw", **changes: Any) -> Grenade:
    base = Grenade(
        name=name,
        desc=desc,
        kind=GrenadeKind.SMOKE,
        pos=[1.0, 2.0, 3.0],
        ang=[-12.0, 90.0],
        source_id=f"dust2_CT/dust2_CT.txt/{name}",
        aim_point=[10.0, 20.0, 30.0],
    )
    return dataclasses.replace(base, **changes)


def sensory(grenades: list[Grenade], map_name: str = "de_dust2") -> list[dict[str, Any]]:
    documents = SensoryExporter(Path("unused")).render({map_name: grenades})
    return documents[f"{map_name}.json"]["lineups"]


@pytest.mark.parametrize(
    ("desc", "expected"),
    [
        ("crouched Jumpthrow", ("crouched", "primary")),
        ("walking M2 throw", ("standing", "secondary")),
        ("crouch-walking M1 + M2 JT", ("crouched", "both")),
        ("crouched line-up, then running M2 Jumpthrow", ("standing", "secondary")),
        ("crouched throw \n line-up while standing", ("crouched", "primary")),
        ("running Jumpthrow (throw Molotov first, then HE)", ("standing", "primary")),
        ("run left, then standing M1+M2 throw", ("standing", "both")),
    ],
)
def test_sensory_actions_follow_the_throw_instruction(desc: str, expected: tuple[str, str]) -> None:
    lineup = sensory([grenade(desc=desc)])[0]

    assert (lineup["stance"], lineup["throw"]) == expected
    assert lineup["movement"] == "stationary"
    assert lineup["manual_action"] is True
    assert lineup["notes"] == desc


def test_sensory_omits_missing_aim_point() -> None:
    lineups = sensory([grenade(aim_point=None), grenade(name="With aim point")])

    assert "aim_point" not in lineups[0]
    assert lineups[1]["aim_point"] == [10.0, 20.0, 30.0]


def test_sensory_ids_distinguish_source_files_reusing_node_ids() -> None:
    ct = grenade(source_id="nuke_CT/nuke_CT.txt/main")
    t = grenade(source_id="nuke_T/nuke_T.txt/main")

    ids = [lineup["id"] for lineup in sensory([ct, t], map_name="de_nuke")]

    assert ids[0] != ids[1]


def test_sensory_ids_survive_reordering_and_note_edits_but_distinguish_maps() -> None:
    first, second = grenade(name="Smoke"), grenade(name="Second smoke")

    before = {lineup["name"]: lineup["id"] for lineup in sensory([first, second])}
    after = {
        lineup["name"]: lineup["id"]
        for lineup in sensory([second, dataclasses.replace(first, desc="Updated notes")])
    }

    assert before == after
    assert before["Smoke"] != before["Second smoke"]
    assert sensory([first], map_name="de_cache")[0]["id"] != before["Smoke"]
