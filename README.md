# Nades Helper

Nades Helper converts CS2 grenade annotation files from KV3/TXT format into JSON files grouped by map.

The nade data is pulled from the CSAFAP config package:

https://github.com/FNScence/CSAFAP-config-package/tree/main/csafap/csgo/annotations/local

## Requirements

- Windows
- Python 3.11 or newer
- Internet connection for the first install and nade updates

## Installation

Run:

```bat
install.bat
```

This creates the local Python environment in `env/` and installs the dependencies from `requirements.txt`.

## Update Nades

Run:

```bat
update_nades.bat
```

This downloads the latest nade annotation files from GitHub and replaces the local `nades/` folder.

Expected source layout:

```text
nades/
  ancient_CT/
    ancient_CT.txt
  ancient_T/
    ancient_T.txt
  cache/
    cache.txt
  train/
    train.txt
```

Folders ending in `_instant_smoke` (case-insensitive) are ignored: their lineups are already included in the main map folders. They are not merged or exported as separate maps. Regenerating HBN or Sensory also removes their legacy `*_instant_smoke.json` output files.

## Generate JSON

Run:

```bat
start.bat
```

This executes `script.py` and writes all generated formats into `out/`.

Example output:

```text
out/default/nades.json
out/hbn/de_ancient.json
out/hbn/de_anubis.json
out/hbn/de_cache.json
out/hbn/de_dust2.json
out/secretservice/grenade_helper.json
out/sensory/de_ancient.json
out/sensory/de_dust2.json
```

## Manual Usage

After running `install.bat`, you can also run the converter manually:

```bat
env\Scripts\python.exe script.py
```

Optional custom paths:

```bat
env\Scripts\python.exe script.py --input-dir nades --output-dir out
```

By default, all formats are generated. You can limit the output to one format:

```bat
env\Scripts\python.exe script.py --format default
env\Scripts\python.exe script.py --format hbn
env\Scripts\python.exe script.py --format secretservice
env\Scripts\python.exe script.py --format sensory
```

## Sensory Export

Sensory receives one JSON file per map in `out/sensory/`, with `version: 1`, the game map name, and a `lineups` array.

- `desc` becomes `notes`, preserving the original text. As in the other formats, the first aim-target description takes precedence over the main annotation description.
- `pos` becomes `origin`; the first two aim angles become `view_angle`.
- `target_end` is included only when the source has a linked destination position. It is not the aim-target position.
- IDs are generated deterministically from the map, relative source filename, and annotation ID. They remain stable across repeated conversions, lineup reordering, and note edits.
- `jump_throw` is enabled by the source `JumpThrow` flag or a recognized description such as `jt`, `J.T.`, `JumpThrow`, `jump throw`, `jump-throw`, or `jump_throw`, regardless of case.
- Annotations missing a position or view angle are excluded during shared parsing for every format (`default`, HBN, SecretService, and Sensory). A warning identifies the annotation and source file; no coordinates are invented.

### Grenade and Action Values

| Source grenade | Sensory value |
| --- | --- |
| Smoke | `smoke` |
| Molotov / incendiary / fire | `fire` |
| HE | `grenade` (provisional) |
| Flashbang | `flash` (provisional) |

Movement, stance, and mouse-button mode are inferred from recognizable description cues:

| Field | Inferred values |
| --- | --- |
| `movement` | `stationary`, `walking`, `running` |
| `stance` | `standing`, `crouched` |
| `throw` | `primary` (M1 or unspecified), `secondary` (M2), `both` (M1+M2) |

The inference distinguishes setup instructions such as `crouched line-up, then standing throw` from the actual throw, and ignores hints after the throw. Unspecified settings use `stationary`, `standing`, and `primary`. The complete description remains in `notes`; this is a heuristic, not a full parser of every possible instruction.

**The HE/flash names and non-template action values are provisional, pending confirmation from the Sensory developer.** They are inferred choices, not a verified Sensory schema. Imports have not been tested inside Sensory.

### Fixed Template Values

| Field | Value |
| --- | --- |
| `angle_tolerance` | `0.11999999731779099` |
| `landing_tolerance` | `24.0` |
| `manual_action` | `false` |
| `max_speed` | `8.0` |
| `position_tolerance` | `4.0` |
| `vertical_tolerance` | `3.0` |

These values remain fixed, including for moving lineups, until the Sensory developer confirms otherwise.

## Tests

Run the regression tests locally:

```bat
env\Scripts\python.exe -m unittest -v test_script
```

The `Tests` GitHub Actions workflow runs on pull requests and pushes to `main`, with read-only repository permissions. The `Sync nades` workflow also runs the tests before updating nade files, generating outputs, or committing changes.

## Project Structure

```text
install.bat        Install Python dependencies
update_nades.bat   Download latest nade files
start.bat          Generate JSON files
script.py          KV3 to JSON converter
test_script.py     Regression tests for Sensory and source discovery
requirements.txt   Python dependencies
nades/             Downloaded source nade files
out/               Generated JSON files
```

## Recommended Workflow

```bat
install.bat
update_nades.bat
start.bat
```

Run `update_nades.bat` again whenever you want to refresh the nade data.
