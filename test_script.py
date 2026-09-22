import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from script import (
    SensoryExporter,
    build_grenades,
    convert_sources,
    selected_exporters,
)


class SensoryExporterTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.exporter = SensoryExporter(self.output_dir)
        self.source = {
            "MapAnnotationNode0": {
                "Type": "grenade",
                "SubType": "main",
                "Id": "main-smoke",
                "Title": {"Text": "Smoke"},
                "Desc": {"Text": "standing throw"},
                "GrenadeType": "smoke",
                "Position": [1.0, 2.0, 3.0],
                "JumpThrow": False,
            },
            "MapAnnotationNode1": {
                "Type": "grenade",
                "SubType": "aim_target",
                "MasterNodeId": "main-smoke",
                "Angles": [-12.0, 90.0, 0.0],
                "Position": [10.0, 20.0, 30.0],
                "Desc": {"Text": "standing W-Jumpthrow"},
            },
        }

    def export_lineups(self, grenades, map_name="dust2"):
        paths = self.exporter.export({map_name: grenades})
        return json.loads(paths[0].read_text(encoding="utf-8"))["lineups"]

    def test_jump_throw_uses_description_or_explicit_flag(self):
        grenades = build_grenades(self.source, "dust2_CT/dust2_CT.txt")
        self.assertTrue(self.export_lineups(grenades)[0]["jump_throw"])

        self.source["MapAnnotationNode1"]["Desc"]["Text"] = "standing throw"
        self.source["MapAnnotationNode0"]["JumpThrow"] = True
        grenades = build_grenades(self.source, "dust2_CT/dust2_CT.txt")
        self.assertTrue(self.export_lineups(grenades)[0]["jump_throw"])

        self.source["MapAnnotationNode0"]["JumpThrow"] = False
        self.source["MapAnnotationNode0"]["Title"]["Text"] = "Jump Spot"
        grenades = build_grenades(self.source, "dust2_CT/dust2_CT.txt")
        self.assertFalse(self.export_lineups(grenades)[0]["jump_throw"])

    def test_jump_throw_spellings_match_whole_words(self):
        cases = {
            "jt": True,
            "JT": True,
            "standing W-JumpThrow": True,
            "jump throw": True,
            "jump-throw": True,
            "jump_throw": True,
            "J.T.": True,
            "jumping throw": True,
            "adjust crosshair": False,
            "jumpthrowing": False,
            "jump onto the ledge, then throw": False,
        }
        for desc, expected in cases.items():
            with self.subTest(desc=desc):
                self.source["MapAnnotationNode1"]["Desc"]["Text"] = desc
                grenades = build_grenades(self.source, "dust2_CT/dust2_CT.txt")
                lineup = self.export_lineups(grenades)[0]
                self.assertEqual(lineup["jump_throw"], expected)

    def test_actions_use_throw_instructions_instead_of_setup_or_later_hints(self):
        cases = (
            ("crouched Jumpthrow", ("crouched", "primary")),
            ("walking M2 throw", ("standing", "secondary")),
            ("crouch-walking M1 + M2 JT", ("crouched", "both")),
            (
                "crouched line-up, then running M2 Jumpthrow",
                ("standing", "secondary"),
            ),
            (
                "crouched throw \n line-up while standing",
                ("crouched", "primary"),
            ),
            (
                "running Jumpthrow (throw Molotov first, then HE)",
                ("standing", "primary"),
            ),
            (
                "run left, then standing M1+M2 throw",
                ("standing", "both"),
            ),
        )
        for desc, expected in cases:
            with self.subTest(desc=desc):
                self.source["MapAnnotationNode1"]["Desc"]["Text"] = desc
                grenades = build_grenades(self.source, "dust2_CT/dust2_CT.txt")
                lineup = self.export_lineups(grenades)[0]
                self.assertEqual((lineup["stance"], lineup["throw"]), expected)
                self.assertEqual(lineup["movement"], "stationary")
                self.assertIs(lineup["manual_action"], True)

    def test_missing_aim_point_is_omitted_without_dropping_the_lineup(self):
        del self.source["MapAnnotationNode1"]["Position"]
        grenades = build_grenades(self.source, "dust2_CT/dust2_CT.txt")
        lineup = self.export_lineups(grenades)[0]
        self.assertNotIn("aim_point", lineup)

    def test_destination_before_main_is_not_confused_with_aim_position(self):
        source = {
            "MapAnnotationNode2": {
                "Type": "grenade",
                "SubType": "destination",
                "MasterNodeId": "main-smoke",
                "Position": [100.0, 200.0, 300.0],
            },
            "MapAnnotationNode3": {
                "Type": "grenade",
                "SubType": "destination",
                "MasterNodeId": "unrelated-main",
                "Position": [400.0, 500.0, 600.0],
            },
            **self.source,
        }
        grenades = build_grenades(source, "dust2_CT/dust2_CT.txt")
        lineup = self.export_lineups(grenades)[0]
        self.assertNotIn("target_end", lineup)
        self.assertEqual(lineup["aim_point"], [10.0, 20.0, 30.0])

    def test_ids_distinguish_source_node_ids_reused_between_teams(self):
        ct_grenades = build_grenades(self.source, "nuke_CT/nuke_CT.txt")
        t_grenades = build_grenades(self.source, "nuke_T/nuke_T.txt")
        lineups = self.export_lineups(ct_grenades + t_grenades, map_name="nuke")
        self.assertNotEqual(lineups[0]["id"], lineups[1]["id"])

    def test_ids_survive_reordering_and_note_edits_but_distinguish_maps(self):
        smoke = build_grenades(self.source, "dust2_CT/dust2_CT.txt")[0]
        second = replace(smoke, source_id="second-smoke", name="Second smoke")
        before = {lineup["name"]: lineup["id"] for lineup in self.export_lineups([smoke, second])}
        after = {
            lineup["name"]: lineup["id"]
            for lineup in self.export_lineups([second, replace(smoke, desc="Updated notes")])
        }
        self.assertEqual(before, after)
        self.assertNotEqual(before["Smoke"], before["Second smoke"])
        cache_id = self.export_lineups([smoke], map_name="cache")[0]["id"]
        self.assertNotEqual(before["Smoke"], cache_id)


class AnnotationValidationTests(unittest.TestCase):
    def test_incomplete_annotations_are_excluded_from_every_export(self):
        main = {
            "Type": "grenade",
            "SubType": "main",
            "Id": "valid",
            "Title": {"Text": "Usable lineup"},
            "GrenadeType": "smoke",
            "Position": [0.0, 0.0, 0.0],
        }
        aim = {
            "Type": "grenade",
            "SubType": "aim_target",
            "MasterNodeId": "valid",
            "Angles": [0.0, 0.0, 0.0],
        }
        source = {
            "MapAnnotationNode0": main,
            "MapAnnotationNode1": aim,
            "MapAnnotationNode2": {
                **main,
                "Id": "no-aim",
                "Title": {"Text": "Missing aim target"},
                "Angles": [0.0, 90.0, 0.0],
            },
            "MapAnnotationNode3": {
                **main,
                "Id": "no-position",
                "Title": {"Text": "Missing position"},
                "Position": None,
            },
            "MapAnnotationNode4": {**aim, "MasterNodeId": "no-position"},
        }
        with self.assertLogs("nades-helper", level="WARNING"):
            grenades = build_grenades(source, "dust2_CT/dust2_CT.txt")

        output_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for exporter in selected_exporters(output_dir, "all"):
            exporter.export({"dust2": grenades})

        for filename, keys, name_key in (
            ("default/nades.json", ("maps", "de_dust2"), "name"),
            ("hbn/de_dust2.json", ("grenades",), "name"),
            ("secretservice/grenade_helper.json", ("spots",), "Name"),
            ("sensory/de_dust2.json", ("lineups",), "name"),
        ):
            with self.subTest(output=filename):
                records = json.loads((output_dir / filename).read_text(encoding="utf-8"))
                for key in keys:
                    records = records[key]
                self.assertEqual([record[name_key] for record in records], ["Usable lineup"])


class MapGroupingTests(unittest.TestCase):
    def test_instant_smoke_packs_are_ignored_and_only_legacy_exports_removed(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        input_dir = root / "nades"
        output_dir = root / "out"
        header = (
            "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
            "format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->\n"
        )
        for folder_name, label in (
            ("anubis_CT", "CT smoke"),
            ("Anubis_Instant_Smoke", "Instant smoke"),
        ):
            folder = input_dir / folder_name
            folder.mkdir(parents=True)
            source = header + f"""
{{
    MapName = "de_anubis"
    MapAnnotationNode0 =
    {{
        Type = "grenade"
        SubType = "main"
        Id = "main-smoke"
        Title = {{ Text = "{label}" }}
        GrenadeType = "smoke"
        Position = [ 1.0, 2.0, 3.0 ]
    }}
    MapAnnotationNode1 =
    {{
        Type = "grenade"
        SubType = "aim_target"
        MasterNodeId = "main-smoke"
        Angles = [ -12.0, 90.0, 0.0 ]
    }}
}}
"""
            (folder / f"{folder_name}.txt").write_text(source, encoding="utf-8")

        for output_format in ("hbn", "sensory"):
            folder = output_dir / output_format
            folder.mkdir(parents=True)
            (folder / "de_anubis_instant_smoke.json").write_text("{}", encoding="utf-8")
            (folder / "unrelated.json").write_text("{}", encoding="utf-8")

        self.assertEqual(convert_sources(input_dir, output_dir, "all"), 0)
        expected_names = ["CT smoke"]
        for output_format, key in (("hbn", "grenades"), ("sensory", "lineups")):
            folder = output_dir / output_format
            self.assertEqual(
                {path.name for path in folder.glob("*.json")},
                {"de_anubis.json", "unrelated.json"},
            )
            payload = json.loads((folder / "de_anubis.json").read_text(encoding="utf-8"))
            self.assertCountEqual([nade["name"] for nade in payload[key]], expected_names)
            if output_format == "sensory":
                self.assertEqual(payload["map"], "de_anubis")
                self.assertEqual({nade["grenade"] for nade in payload[key]}, {"smoke"})

        default_path = output_dir / "default/nades.json"
        maps = json.loads(default_path.read_text(encoding="utf-8"))["maps"]
        self.assertEqual(set(maps), {"de_anubis"})
        self.assertCountEqual([nade["name"] for nade in maps["de_anubis"]], expected_names)

        secret_path = output_dir / "secretservice/grenade_helper.json"
        secret = json.loads(secret_path.read_text(encoding="utf-8"))
        self.assertEqual(secret["knownMaps"], ["<empty>", "de_anubis"])
        self.assertEqual({spot["MapName"] for spot in secret["spots"]}, {"de_anubis"})
        self.assertCountEqual([spot["Name"] for spot in secret["spots"]], expected_names)


if __name__ == "__main__":
    unittest.main()
