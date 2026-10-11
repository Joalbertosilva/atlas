"""Leitura segura de membros ZIP sem extração para disco."""
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

MAX_MEMBER_BYTES = 12 * 1024**3
MAX_RATIO = 250
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")


class UnsafeZipError(ValueError):
    pass


@dataclass(frozen=True)
class Member:
    name: str
    crc32: str
    size: int
    compressed: int


def list_members(path: Path, suffix: str = ".csv") -> list[Member]:
    out = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if "/" in name or "\\" in name or ".." in name or not _SAFE_NAME.match(name):
                raise UnsafeZipError(f"nome de membro inseguro: {name!r}")
            if info.file_size > MAX_MEMBER_BYTES:
                raise UnsafeZipError(f"membro grande demais: {name} ({info.file_size} bytes)")
            if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
                raise UnsafeZipError(f"taxa de compressão suspeita em {name}")
            if name.lower().endswith(suffix):
                out.append(Member(name, f"{info.CRC:08x}", info.file_size, info.compress_size))
    return out


def open_member(path: Path, name: str):
    z = zipfile.ZipFile(path)
    return z, z.open(name)
