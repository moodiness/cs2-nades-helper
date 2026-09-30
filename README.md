# Nades Helper

Nades Helper converts CS2 grenade annotation files (KV3) into JSON files for grenade-helper plugins.

The nade data comes from the CSAFAP config package:

https://github.com/FNScence/CSAFAP-config-package/tree/main/csafap/csgo/annotations/local

The `Sync nades` GitHub Actions workflow refreshes `nades/` and regenerates `out/` every 30
minutes, so the committed JSON files are always up to date.

## Requirements

- Python 3.11 or newer
- Internet connection for the install and nade updates

## Installation

```sh
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

## Usage

```sh
nades-helper update              # download the latest annotation files into nades/
nades-helper build               # generate every JSON format into out/
```

`python -m nades_helper <command>` works the same way. Add `-v` for debug details or `-q` for
warnings and errors only.

### `build`

| Option | Default | Description |
| --- | --- | --- |
| `--input-dir` | `nades` | Folder containing one sub-folder per annotation file |
| `--output-dir` | `out` | Folder receiving one sub-folder per format |
| `--format` | all | `default`, `hbn`, `secretservice` or `sensory`; repeatable |

Files are written atomically and left untouched when their content did not change. If any
annotation file fails to parse, nothing is written.

### `update`

| Option | Default | Description |
| --- | --- | --- |
| `--nades-dir` | `nades` | Folder replaced with the downloaded annotation files |
| `--url` | CSAFAP `main` branch zip | Archive to download |
| `--source-path` | `csafap/csgo/annotations/local` | Annotation folder inside the archive |
| `--timeout` | `60` | Network timeout in seconds |

The archive is downloaded and extracted next to `nades/` first; the folder is only swapped once
extraction succeeded, so a failed update never leaves partial data. The log lists how many files
were added, removed and changed.

## Source layout

```text
nades/
  ancient_CT/ancient_CT.txt     side CT
  ancient_T/ancient_T.txt       side T
  cache/cache.txt               no side
```

- The map comes from the file name: `ancient_CT.txt` becomes `de_ancient`.
- Within a map, grenades are ordered CT files first, then T, then side-less files, then file order.
- A folder contributes `<folder>.txt`, or every `.txt` it contains when that file is missing.
- Folders ending in `_instant_smoke` (case-insensitive) are ignored: their lineups are already
  included in the main map folders. Building HBN or Sensory also removes their legacy
  `*_instant_smoke.json` files; other files in the output folders are left alone.

## Conversion rules

Every `grenade` node with `SubType = "main"` is a throwing position; its `aim_target` nodes
(linked through `MasterNodeId`) are the aims.

- One lineup is exported per aim target, so a position with two throws yields two lineups.
- `desc` is the aim target description, or the main node description when empty.
- Lineups missing a position or aim angles are excluded from every format; no coordinates are
  invented. The log counts them (details with `-v`).
- When a file reuses the same main `Id`, aim targets belong to the closest preceding main node.
- `GrenadeType = "fire"` is treated as `molotov`; unknown types are skipped with a warning.
- Nodes with `Enabled = false` are ignored.

## Output formats

```text
out/default/nades.json                  {"version": 1, "maps": {"de_ancient": [...]}}
out/hbn/de_<map>.json                   {"grenades": [...]}
out/secretservice/grenade_helper.json   {"knownMaps": ["<empty>", ...], "spots": [...]}
out/sensory/de_<map>.json               {"lineups": [...], "map": "de_<map>", "version": 1}
```

`default` and `hbn` entries use CS weapon ids for `type`: flash `43`, HE `44`, smoke `45`,
molotov/incendiary `46`. `secretservice` uses names (`smoke`, `flash`, `hegrenade`, `molotov`,
`incendiary`).

### Sensory

- `desc` becomes `notes`, preserving the original text.
- `pos` becomes `origin`; the first two aim angles become `view_angle`.
- `aim_point` comes from the same aim-target node as `view_angle`. If its position is
  unavailable, the field is omitted, never `null` and never replaced with invented coordinates.
- IDs are generated deterministically from the map, relative source filename, and annotation
  ID. They remain stable across repeated conversions, lineup reordering, and note edits. When a
  position has several aim targets, the first keeps this ID and the next ones are derived from
  it with a `#2`, `#3`... suffix.
- `jump_throw` is enabled by the source `JumpThrow` flag or a recognized description such as
  `jt`, `J.T.`, `JumpThrow`, `jump throw`, `jump-throw`, or `jump_throw`, regardless of case.

| Source grenade | Sensory value |
| --- | --- |
| Smoke | `smoke` |
| Molotov / incendiary / fire | `fire` |
| HE | `he` |
| Flashbang | `flash` |

Stance and mouse-button mode are inferred from recognizable description cues. For manual use,
`movement` is always forced to `stationary` and `manual_action` to `true`, even when the notes
describe movement.

| Field | Output values |
| --- | --- |
| `movement` | `stationary` (forced) |
| `stance` | `standing`, `crouched` |
| `throw` | `primary` (M1 or unspecified), `secondary` (M2), `both` (M1+M2) |

The inference distinguishes setup instructions such as `crouched line-up, then standing throw`
from the actual throw, and ignores hints after the throw. Unspecified stance and button mode use
`standing` and `primary`. The complete description remains in `notes`, including walking,
running, and directional instructions to follow manually; this is a heuristic, not a full parser
of every possible instruction.

The grenade, stance, and throw enum names match values observed in the developer-provided
Sensory export. Description interpretation remains heuristic, and imports have not been tested
inside Sensory.

| Fixed setting | Value |
| --- | --- |
| `angle_tolerance` | `0.11999999731779099` |
| `landing_tolerance` | `24.0` |
| `manual_action` | `true` |
| `max_speed` | `8.0` |
| `position_tolerance` | `4.0` |
| `vertical_tolerance` | `3.0` |

These are deliberately fixed export settings, not universal Sensory constants. In particular,
`position_tolerance: 4.0` is a conservative default; the developer-provided lineups use values
from `1.0` to `10.0`.

## Development

```sh
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest
```

The `Tests` workflow runs the same checks on pull requests and pushes to `main`, with read-only
repository permissions. `Sync nades` runs the tests before updating annotations and outputs.

```text
nades_helper/
  cli.py          argument parsing, logging setup, exit codes
  build.py        build pipeline and log summaries
  sources.py      discovery of annotation files, sides and map names
  annotations.py  KV3 loading and lineup extraction
  throws.py       jump-throw, stance and mouse-button heuristics
  exporters.py    default / hbn / secretservice / sensory JSON formats
  update.py       CSAFAP download and atomic folder swap
tests/            pytest suite
```
