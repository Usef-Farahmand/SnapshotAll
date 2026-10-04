"""The version number must be the same everywhere it is shown."""
import subprocess
import sys
from pathlib import Path

import set_version as sv

ROOT = Path(__file__).resolve().parent.parent


def test_default_version_is_read_from_snapshot_common():
    assert sv.default_version() == _default_in_source()


def _default_in_source():
    import re
    return re.search(r'^_DEFAULT_VERSION = "([^"]+)"', (ROOT / "snapshot_common.py").read_text(), re.M).group(1)


def test_ci_versions():
    d = "1.4.1"
    assert sv.compute_version("refs/tags/v1.5.0", "v1.5.0", "99", d) == "1.5.0"          # tag: exactly the tag
    assert sv.compute_version("refs/heads/main", "main", "57", d) == "1.4.57"            # main: MAJOR.MINOR.RUN
    assert sv.compute_version("refs/heads/develop", "develop", "12", d) == "1.4.0-dev.12"
    assert sv.compute_version("refs/pull/3/merge", "3/merge", "13", d) == "1.4.0-dev.13"


def test_numeric_version_for_windows():
    assert sv.numeric_version("1.4.57") == (1, 4, 57, 0)
    assert sv.numeric_version("1.4.0-dev.12") == (1, 4, 0, 12)
    assert sv.numeric_version("2") == (2, 0, 0, 0)


def test_version_info_file_carries_the_same_version():
    text = sv.version_info_text("1.4.57")
    assert "filevers=(1, 4, 57, 0)" in text
    assert "StringStruct('FileVersion', '1.4.57')" in text and "StringStruct('ProductVersion', '1.4.57')" in text


def test_app_header_reads_the_build_version(tmp_path):
    """snapshot_common must show exactly the version that tools/set_version.py wrote."""
    (tmp_path / "snapshot_common.py").write_text((ROOT / "snapshot_common.py").read_text(), encoding="utf-8")
    sv.write_files("1.4.57", tmp_path)
    code = "import snapshot_common as c; print(c.APP_VERSION)"
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True,
                         env={"PYTHONPATH": str(tmp_path), "PATH": ""}).stdout.strip()
    assert out == "1.4.57"
    (tmp_path / "_build_version.py").unlink()
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True,
                         env={"PYTHONPATH": str(tmp_path), "PATH": ""}).stdout.strip()
    assert out == _default_in_source()                                                    # local runs: the default


def test_installer_script_has_no_hard_coded_version():
    iss = (ROOT / "installer.iss").read_text()
    assert "AppVersion={#MyAppVersion}" in iss
    import re
    assert not re.search(r"^AppVersion=\d", iss, re.M)
