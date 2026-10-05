#!/usr/bin/env python3
"""Single source of truth for the version number.

The default version lives in snapshot_common.py (_DEFAULT_VERSION). For a build, this script decides the
final version, writes it to

  _build_version.py   read by snapshot_common  -> the app header and Settings > About
  version_info.txt    PyInstaller version file -> the Windows file properties of SnapshotAll.exe

and prints it, so the installer (Inno Setup /DMyAppVersion=...) and the GitHub release use the very same string.

  python tools/set_version.py                          the default version
  python tools/set_version.py 1.5.0                    an explicit version
  python tools/set_version.py --ci REF REF_NAME RUN    version of a GitHub Actions build:
                                                         tag vX.Y.Z   -> X.Y.Z
                                                         main branch  -> MAJOR.MINOR.RUN
                                                         other        -> MAJOR.MINOR.0-dev.RUN
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def default_version(root=ROOT):
    text = (Path(root) / "snapshot_common.py").read_text(encoding="utf-8")
    return re.search(r'^_DEFAULT_VERSION = "([^"]+)"', text, re.M).group(1)


def compute_version(ref, ref_name, run_number, default):
    major_minor = ".".join(default.split(".")[:2])
    if ref.startswith("refs/tags/v"):
        return ref_name[1:]
    if ref == "refs/heads/main":
        return f"{major_minor}.{run_number}"
    return f"{major_minor}.0-dev.{run_number}"


def numeric_version(version):
    """'1.4.37' -> (1, 4, 37, 0);  '1.4.0-dev.12' -> (1, 4, 0, 12)  (Windows wants four numbers)."""
    nums = [int(n) for n in re.findall(r"\d+", version.split("-")[0])][:3]
    nums += [0] * (3 - len(nums))
    build = re.search(r"-[A-Za-z]+\.(\d+)", version)
    return (*nums, int(build.group(1)) if build else 0)


def version_info_text(version):
    nums = numeric_version(version)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Usef Farahmand'),
      StringStruct('FileDescription', 'SnapshotAll'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'SnapshotAll'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Usef Farahmand'),
      StringStruct('OriginalFilename', 'SnapshotAll.exe'),
      StringStruct('ProductName', 'SnapshotAll'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def write_files(version, root=ROOT):
    root = Path(root)
    (root / "_build_version.py").write_text(f'APP_VERSION = "{version}"\n', encoding="utf-8")
    (root / "version_info.txt").write_text(version_info_text(version), encoding="utf-8")


def main(argv):
    default = default_version()
    if argv[:1] == ["--ci"]:
        version = compute_version(argv[1], argv[2], argv[3], default)
    elif argv:
        version = argv[0].lstrip("v")
    else:
        version = default
    write_files(version)
    print(version)


if __name__ == "__main__":
    main(sys.argv[1:])
