import io
import zipfile
from pathlib import Path

import pytest

from atlas_etl.zipsafe import UnsafeZipError, list_members


def _zip_with(tmp: Path, name: str, data: bytes) -> Path:
    zpath = tmp / "t.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr(name, data)
    return zpath


def test_list_members_accepts_safe_csv(tmp_path):
    p = _zip_with(tmp_path, "votacao_secao_2026_AC.csv", b"a;b\n1;2\n")
    members = list_members(p)
    assert [m.name for m in members] == ["votacao_secao_2026_AC.csv"]


def test_rejects_path_traversal(tmp_path):
    zpath = tmp_path / "bad.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        info = zipfile.ZipInfo("../etc/passwd")
        z.writestr(info, b"x")
    with pytest.raises(UnsafeZipError):
        list_members(zpath)


def test_rejects_nested_path(tmp_path):
    p = _zip_with(tmp_path, "dir/file.csv", b"x")
    with pytest.raises(UnsafeZipError):
        list_members(p)
