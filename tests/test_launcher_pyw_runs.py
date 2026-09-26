import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
LAUNCHER = REPO_ROOT / "launcher" / "launcher.pyw"


def test_launcher_pyw_starts_without_import_error():
    """Regression test: launcher.pyw is normally started by double-clicking
    a shortcut (pythonw.exe launcher.pyw directly, working directory = repo
    root), which is a DIFFERENT import context than pytest's -- Python sets
    sys.path[0] to launcher/'s OWN directory for direct script execution,
    not the repo root. A package-style `from launcher.trip_archive import
    ...` broke under that direct-execution context: since .pyw is a
    recognized import source suffix on this platform
    (importlib.machinery.SOURCE_SUFFIXES), Python's import system resolved
    the top-level name "launcher" to the file launcher/launcher.pyw itself
    (sitting in sys.path[0]) instead of the real launcher/ package,
    producing "ModuleNotFoundError: 'launcher' is not a package". No
    existing test caught this because every other test/verification in
    this repo imports launcher.pyw via importlib.util.spec_from_file_location
    or runs pytest from the repo root -- neither reproduces a real direct
    script invocation's sys.path[0]."""
    proc = subprocess.Popen(
        [str(PYTHON_EXE), str(LAUNCHER)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # A successful start blocks in Tk's mainloop; only a startup
        # failure (e.g. an import error before mainloop even begins)
        # exits within this short window.
        stdout, stderr = proc.communicate(timeout=3)
        raise AssertionError(
            f"launcher.pyw exited early (code {proc.returncode}); stderr:\n{stderr}"
        )
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=5)
