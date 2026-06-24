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

## Generate JSON

Run:

```bat
start.bat
```

This executes `script.py` and writes the generated JSON files into `out/`.

Example output:

```text
out/de_ancient.json
out/de_anubis.json
out/de_cache.json
out/de_dust2.json
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

## Project Structure

```text
install.bat        Install Python dependencies
update_nades.bat   Download latest nade files
start.bat          Generate JSON files
script.py          KV3 to JSON converter
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
