"""Proste GUI do odpalania aplikacji Borowik bez terminala.

Uruchamiane przez pythonw.exe (bez konsoli). Odpala pipeline.prepare_trip,
npm run sync-data i npm run dev, po czym otwiera przegladarke.
"""
from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
CONFIG_PATH = Path(__file__).resolve().parent / "launcher_config.json"
DEV_URL = "http://127.0.0.1:5173"

DEFAULT_CONFIG = {"lat": "53.1509", "lon": "16.7382", "radius_km": "25"}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(values: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def server_is_up() -> bool:
    try:
        urllib.request.urlopen(DEV_URL, timeout=1)
        return True
    except Exception:
        return False


class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Borowik - launcher")
        self.root.geometry("640x460")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.dev_process: subprocess.Popen | None = None
        self.worker_running = False

        config = load_config()

        form = ttk.Frame(root, padding=10)
        form.pack(fill="x")

        ttk.Label(form, text="Szerokosc (lat):").grid(row=0, column=0, sticky="w")
        self.lat_var = tk.StringVar(value=config["lat"])
        ttk.Entry(form, textvariable=self.lat_var, width=15).grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(form, text="Dlugosc (lon):").grid(row=0, column=2, sticky="w")
        self.lon_var = tk.StringVar(value=config["lon"])
        ttk.Entry(form, textvariable=self.lon_var, width=15).grid(row=0, column=3, sticky="w", padx=5)

        ttk.Label(form, text="Promien (km, 10-50):").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.radius_var = tk.StringVar(value=config["radius_km"])
        ttk.Entry(form, textvariable=self.radius_var, width=15).grid(row=1, column=1, sticky="w", padx=5, pady=(6, 0))

        buttons = ttk.Frame(root, padding=(10, 0))
        buttons.pack(fill="x")
        self.run_button = ttk.Button(buttons, text="Uruchom analize i podglad", command=self.on_run_full)
        self.run_button.pack(side="left")
        self.preview_button = ttk.Button(buttons, text="Tylko podglad", command=self.on_run_preview)
        self.preview_button.pack(side="left", padx=8)
        self.stop_button = ttk.Button(buttons, text="Zatrzymaj serwer", command=self.stop_server)
        self.stop_button.pack(side="left")

        self.status_var = tk.StringVar(value="Gotowy.")
        ttk.Label(root, textvariable=self.status_var, padding=(10, 6)).pack(fill="x")

        log_frame = ttk.Frame(root, padding=(10, 0, 10, 10))
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=16, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(200, self.drain_log_queue)

    def log(self, message: str) -> None:
        self.log_queue.put(message)

    def drain_log_queue(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(200, self.drain_log_queue)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def validate_inputs(self) -> tuple[float, float, float] | None:
        try:
            lat = float(self.lat_var.get())
            lon = float(self.lon_var.get())
            radius = float(self.radius_var.get())
        except ValueError:
            messagebox.showerror("Blad", "Lat/lon/promien musza byc liczbami.")
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            messagebox.showerror("Blad", "Lat musi byc w [-90, 90], lon w [-180, 180].")
            return None
        if not (10 <= radius <= 50):
            messagebox.showerror("Blad", "Promien musi byc w zakresie 10-50 km.")
            return None
        return lat, lon, radius

    def on_run_full(self) -> None:
        values = self.validate_inputs()
        if values is None:
            return
        if self.worker_running:
            messagebox.showinfo("Info", "Poprzednie zadanie jeszcze trwa.")
            return
        lat, lon, radius = values
        save_config({"lat": str(lat), "lon": str(lon), "radius_km": str(radius)})
        self.worker_running = True
        self.set_buttons_enabled(False)
        threading.Thread(target=self.run_full_pipeline, args=(lat, lon, radius), daemon=True).start()

    def on_run_preview(self) -> None:
        if self.worker_running:
            messagebox.showinfo("Info", "Poprzednie zadanie jeszcze trwa.")
            return
        self.worker_running = True
        self.set_buttons_enabled(False)
        threading.Thread(target=self.run_preview_only, daemon=True).start()

    def set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.run_button.configure(state=state)
        self.preview_button.configure(state=state)

    def run_command(self, cmd: list[str], cwd: Path) -> bool:
        self.log(f"$ {' '.join(cmd)}")
        try:
            process = subprocess.Popen(
                cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError as exc:
            self.log(f"Nie udalo sie odpalic: {exc}")
            return False
        assert process.stdout is not None
        for line in process.stdout:
            self.log(line.rstrip())
        return process.wait() == 0

    def run_full_pipeline(self, lat: float, lon: float, radius: float) -> None:
        try:
            self.set_status("Uruchamiam analize pipeline...")
            ok = self.run_command(
                [str(PYTHON_EXE), "-m", "pipeline.prepare_trip",
                 "--lat", str(lat), "--lon", str(lon), "--radius-km", str(radius)],
                cwd=REPO_ROOT,
            )
            if not ok:
                self.set_status("Analiza sie nie powiodla - zobacz log.")
                return
            self.set_status("Synchronizuje dane do frontendu...")
            ok = self.run_command(["npm.cmd", "run", "sync-data"], cwd=FRONTEND_DIR)
            if not ok:
                self.set_status("Synchronizacja danych sie nie powiodla - zobacz log.")
                return
            self.ensure_dev_server_and_open()
        finally:
            self.worker_running = False
            self.set_buttons_enabled(True)

    def run_preview_only(self) -> None:
        try:
            self.ensure_dev_server_and_open()
        finally:
            self.worker_running = False
            self.set_buttons_enabled(True)

    def ensure_dev_server_and_open(self) -> None:
        if server_is_up():
            self.log("Serwer juz dziala.")
        else:
            self.set_status("Startuje serwer frontendu...")
            self.log("$ npm.cmd run dev")
            try:
                self.dev_process = subprocess.Popen(
                    ["npm.cmd", "run", "dev"], cwd=str(FRONTEND_DIR),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except OSError as exc:
                self.log(f"Nie udalo sie odpalic npm run dev: {exc}")
                self.set_status("Blad startu serwera.")
                return
            threading.Thread(target=self.pump_dev_output, daemon=True).start()
            for _ in range(60):
                if server_is_up():
                    break
                time.sleep(0.5)
            else:
                self.set_status("Serwer nie odpowiedzial w czasie - zobacz log.")
                return
        self.set_status(f"Otwieram {DEV_URL}")
        webbrowser.open(DEV_URL)
        self.set_status("Gotowe.")

    def pump_dev_output(self) -> None:
        if self.dev_process is None or self.dev_process.stdout is None:
            return
        for line in self.dev_process.stdout:
            self.log(line.rstrip())

    def stop_server(self) -> None:
        if self.dev_process is not None and self.dev_process.poll() is None:
            # npm.cmd spawns node.exe as a child process; terminate() only
            # kills the npm.cmd wrapper and leaves node.exe (Vite) listening
            # on the port. taskkill /T kills the whole process tree.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self.dev_process.pid)],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.log("Zatrzymano serwer frontendu.")
            self.dev_process = None
            self.set_status("Serwer zatrzymany.")
        else:
            self.log("Serwer nie jest uruchomiony przez ten launcher.")

    def on_close(self) -> None:
        self.stop_server()
        self.root.destroy()


def main() -> None:
    if not PYTHON_EXE.exists():
        messagebox.showerror("Blad", f"Nie znaleziono {PYTHON_EXE}. Uruchom najpierw uv sync.")
        sys.exit(1)
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
