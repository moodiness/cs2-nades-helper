from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from nades_helper.errors import NadesHelperError
from nades_helper.update import run_update

SOURCE_PATH = "csafap/csgo/annotations/local"
ROOT = "CSAFAP-config-package-main"


def make_archive(path: Path, files: dict[str, str]) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path.as_uri()


def tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in root.rglob("*")
        if p.is_file()
    }


def test_update_replaces_folder_with_annotation_subtree(tmp_path: Path) -> None:
    nades = tmp_path / "nades"
    (nades / "old_T").mkdir(parents=True)
    (nades / "old_T" / "old_T.txt").write_text("old", encoding="utf-8")
    (nades / "mirage_T").mkdir()
    (nades / "mirage_T" / "mirage_T.txt").write_text("v1", encoding="utf-8")
    url = make_archive(
        tmp_path / "source.zip",
        {
            f"{ROOT}/README.md": "ignored",
            f"{ROOT}/{SOURCE_PATH}/mirage_T/mirage_T.txt": "v2",
            f"{ROOT}/{SOURCE_PATH}/nuke_CT/nuke_CT.txt": "new",
        },
    )

    changes = run_update(nades, url=url, source_path=SOURCE_PATH)

    assert tree(nades) == {"mirage_T/mirage_T.txt": "v2", "nuke_CT/nuke_CT.txt": "new"}
    assert changes.added == ["nuke_CT/nuke_CT.txt"]
    assert changes.removed == ["old_T/old_T.txt"]
    assert changes.changed == ["mirage_T/mirage_T.txt"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["nades", "source.zip"]


def test_update_keeps_existing_folder_when_archive_has_no_annotations(tmp_path: Path) -> None:
    nades = tmp_path / "nades"
    nades.mkdir()
    (nades / "keep.txt").write_text("keep", encoding="utf-8")
    url = make_archive(tmp_path / "source.zip", {f"{ROOT}/other/file.txt": "x"})

    with pytest.raises(NadesHelperError, match="No annotation files"):
        run_update(nades, url=url, source_path=SOURCE_PATH)

    assert tree(nades) == {"keep.txt": "keep"}


def test_update_rejects_paths_escaping_the_destination(tmp_path: Path) -> None:
    url = make_archive(tmp_path / "source.zip", {f"{ROOT}/{SOURCE_PATH}/../../../../evil.txt": "x"})

    with pytest.raises(NadesHelperError, match="Unsafe path"):
        run_update(tmp_path / "nades", url=url, source_path=SOURCE_PATH)

    assert not (tmp_path / "evil.txt").exists()


def test_update_reports_download_errors(tmp_path: Path) -> None:
    with pytest.raises(NadesHelperError, match="Download failed"):
        run_update(tmp_path / "nades", url=(tmp_path / "missing.zip").as_uri())
