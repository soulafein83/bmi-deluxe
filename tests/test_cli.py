import json
import subprocess
import sys
from pathlib import Path


def _run(*args):
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "bmi.py"), *args],
        capture_output=True, text=True,
    )


def test_cli_json():
    r = _run("-w", "70", "-z", "1.75", "--json", "--bez-historii")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["bmi"] == 22.86
    assert data["kategoria"] == "Prawidłowa masa"


def test_cli_edytuj(tmp_path):
    hist = tmp_path / "h.json"
    r = _run("-w", "70", "-z", "1.75", "--historia", str(hist))
    assert r.returncode == 0
    r = _run("--edytuj", "0", "--waga", "80", "--wzrost", "1.8",
             "--historia", str(hist))
    assert r.returncode == 0
    import json as _j
    data = _j.loads(hist.read_text())
    assert data[0]["waga"] == 80.0
    assert abs(data[0]["bmi"] - 80 / 1.8 ** 2) < 1e-9