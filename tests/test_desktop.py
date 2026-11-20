import os
import subprocess
import sys
from pathlib import Path

import pytest


def _pyside_available():
    try:
        import PySide6  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _pyside_available(), reason="PySide6 not installed")
def test_desktop_smoke():
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["BMI_DESKTOP_SMOKE"] = "1"
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "bmi_desktop.py")],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert r.returncode == 0, r.stderr