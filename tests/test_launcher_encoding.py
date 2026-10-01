import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

LAUNCHER_DIR = Path(__file__).resolve().parent.parent / "launcher"


def _load_launcher():
    # launcher.pyw importuje sasiada `trip_archive` bez pakietu (jak przy uruchomieniu dwuklikiem)
    sys.path.insert(0, str(LAUNCHER_DIR))
    try:
        loader = importlib.machinery.SourceFileLoader("launcher_gui", str(LAUNCHER_DIR / "launcher.pyw"))
        spec = importlib.util.spec_from_loader("launcher_gui", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(LAUNCHER_DIR))


def test_child_process_output_is_decoded_as_utf8():
    """Komunikaty sync-data (Node, UTF-8) byly w logu launchera krzaczkami ("moĹĽna"), bo text=True
    dekodowal je w kodowaniu Windows (cp1250). Procesy Pythona dostaja PYTHONIOENCODING=utf-8."""
    launcher = _load_launcher()
    kwargs = launcher.child_process_kwargs()
    assert kwargs["encoding"] == "utf-8" and kwargs["errors"] == "replace"
    assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
    out = subprocess.run(
        [sys.executable, "-c", "print('Nie można podmienić pliku: wydzieleń')"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs,
    ).stdout
    assert out.strip() == "Nie można podmienić pliku: wydzieleń"
