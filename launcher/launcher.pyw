"""Proste GUI do odpalania aplikacji Borowik bez terminala.

Uruchamiane przez pythonw.exe (bez konsoli). Odpala pipeline.prepare_trip,
npm run sync-data i npm run dev, po czym otwiera przegladarke.
"""
from __future__ import annotations

import json
import os
import queue
import socket
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
# Sibling import, not `from launcher.trip_archive import ...`: launcher.pyw
# is normally started by double-clicking (python[w].exe launcher.pyw
# directly), which puts launcher/ itself -- not the repo root -- at
# sys.path[0]. Since .pyw is a recognized import source suffix on this
# platform, a package-style import of "launcher" resolved to this very
# file (launcher/launcher.pyw, sitting in sys.path[0]) instead of the real
# launcher/ package, breaking with "'launcher' is not a package". A bare
# sibling import needs no sys.path change, because launcher/ is already on
# sys.path for direct execution.
from trip_archive import (
    phone_export_args, read_day, read_index, save_trip, trip_choices, trip_exists, trip_id,
)
FRONTEND_DIR = REPO_ROOT / "frontend"
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
CONFIG_PATH = Path(__file__).resolve().parent / "launcher_config.json"
DEV_URL = "http://127.0.0.1:5173"

def child_process_kwargs() -> dict:
    """Wyjscie procesow potomnych czytane jako UTF-8: Node (sync-data, Vite) pisze w UTF-8, a procesy
    Pythona dostaja PYTHONIOENCODING=utf-8. Samo text=True dekodowalo w kodowaniu Windows (cp1250),
    wiec polskie znaki z komunikatow byly krzaczkami ("moĹĽna")."""
    return {"encoding": "utf-8", "errors": "replace", "env": {**os.environ, "PYTHONIOENCODING": "utf-8"}}


DEFAULT_CONFIG = {"lat": "53.1509", "lon": "16.7382", "radius_km": "25", "place": "", "lan": False}
DEV_PORT = 5173


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(values: dict) -> None:
    # Scalanie z zapisanym plikiem: kazde miejsce zapisu ustawia tylko swoje klucze (np. "lan").
    try:
        CONFIG_PATH.write_text(
            json.dumps({**load_config(), **values}, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def lan_ip() -> str | None:
    """Adres IPv4 tego komputera w sieci lokalnej (UDP connect nic nie wysyla), albo None bez sieci."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def server_is_up(url: str = DEV_URL) -> bool:
    try:
        urllib.request.urlopen(url, timeout=1)
        return True
    except Exception:
        return False


class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Borowik - launcher")
        self.root.geometry("640x500")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.dev_process: subprocess.Popen | None = None
        self.worker_running = False
        self.lan_requested = False

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

        ttk.Label(form, text="Nazwa miejsca:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.place_var = tk.StringVar(value=config["place"])
        ttk.Entry(form, textvariable=self.place_var, width=30).grid(
            row=2, column=1, columnspan=3, sticky="w", padx=5, pady=(6, 0)
        )

        self.lan_var = tk.BooleanVar(value=bool(config.get("lan")))
        ttk.Checkbutton(
            form, text="Udostepnij w sieci lokalnej (inne komputery i telefony)", variable=self.lan_var,
            command=lambda: save_config({"lan": self.lan_var.get()}),
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

        buttons = ttk.Frame(root, padding=(10, 0))
        buttons.pack(fill="x")
        self.run_button = ttk.Button(buttons, text="Uruchom analize i podglad", command=self.on_run_full)
        self.run_button.pack(side="left")
        self.preview_button = ttk.Button(buttons, text="Tylko podglad", command=self.on_run_preview)
        self.preview_button.pack(side="left", padx=8)
        self.stop_button = ttk.Button(buttons, text="Zatrzymaj serwer", command=self.stop_server)
        self.stop_button.pack(side="left")
        self.save_trip_button = ttk.Button(
            buttons, text="Zapisz do listy", command=self.on_save_trip
        )
        self.save_trip_button.pack(side="left", padx=8)

        phone = ttk.Frame(root, padding=(10, 6, 10, 0))
        phone.pack(fill="x")
        self.phone_button = ttk.Button(phone, text="Eksport na telefon", command=self.on_export_phone)
        self.phone_button.pack(side="left")
        ttk.Label(phone, text="Zrodlo:").pack(side="left", padx=(10, 4))
        self.phone_source_var = tk.StringVar()
        self.phone_combo = ttk.Combobox(phone, textvariable=self.phone_source_var, state="readonly", width=46)
        self.phone_combo.pack(side="left")
        self.phone_ids: list[str | None] = [None]
        self.refresh_phone_sources()

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
        save_config({
            "lat": str(lat), "lon": str(lon), "radius_km": str(radius),
            "place": self.place_var.get().strip(),
        })
        self.worker_running = True
        self.lan_requested = self.lan_var.get()
        self.set_buttons_enabled(False)
        threading.Thread(target=self.run_full_pipeline, args=(lat, lon, radius), daemon=True).start()

    def on_run_preview(self) -> None:
        if self.worker_running:
            messagebox.showinfo("Info", "Poprzednie zadanie jeszcze trwa.")
            return
        self.worker_running = True
        self.lan_requested = self.lan_var.get()
        self.set_buttons_enabled(False)
        threading.Thread(target=self.run_preview_only, daemon=True).start()

    def on_save_trip(self) -> None:
        if self.worker_running:
            messagebox.showinfo("Info", "Poprzednie zadanie jeszcze trwa.")
            return
        name = self.place_var.get().strip()
        if not name:
            messagebox.showerror("Blad", "Podaj nazwe miejsca przed zapisem.")
            return
        values = self.validate_inputs()
        if values is None:
            return
        lat, lon, radius = values
        data_dir = FRONTEND_DIR / "public" / "data"
        trips_dir = data_dir / "trips"
        try:
            day = read_day(data_dir / "scores.json")
        except ValueError as exc:
            messagebox.showerror("Blad", str(exc))
            return
        tid = trip_id(name, day)
        if trip_exists(trips_dir, tid) and not messagebox.askyesno(
            "Potwierdzenie",
            f"Wpis '{name}' z dnia {day} juz istnieje. Nadpisac?",
        ):
            self.log("Zapis anulowany (wpis juz istnieje).")
            return
        try:
            meta = save_trip(data_dir, trips_dir, name, radius, lat, lon)
        except (OSError, ValueError) as exc:
            # save_trip can also fail after the confirmation dialog above
            # (disk full, permission denied, an unexpected data shape) --
            # under pythonw there is no console, so an uncaught exception
            # here would fail completely silently (review finding, plan
            # 2026-09-26-borowik-saved-maps).
            messagebox.showerror("Blad", f"Zapis nie powiodl sie: {exc}")
            return
        save_config({
            "lat": str(lat), "lon": str(lon), "radius_km": str(radius), "place": name,
        })
        self.refresh_phone_sources()
        self.log(f"Zapisano '{meta.name} - {meta.radius_km:g}km - {meta.day}' do listy.")
        self.set_status("Zapisano do listy zapisanych map.")

    def set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.run_button.configure(state=state)
        self.preview_button.configure(state=state)
        self.phone_button.configure(state=state)

    def refresh_phone_sources(self) -> None:
        """Lista zrodel eksportu na telefon: biezaca analiza + zapisane migawki (zachowuje wybor)."""
        labels, self.phone_ids = trip_choices(read_index(FRONTEND_DIR / "public" / "data" / "trips" / "index.json"))
        previous = self.phone_source_var.get()
        self.phone_combo.configure(values=labels)
        self.phone_source_var.set(previous if previous in labels else labels[0])

    def on_export_phone(self) -> None:
        if self.worker_running:
            messagebox.showinfo("Info", "Poprzednie zadanie jeszcze trwa.")
            return
        index = self.phone_combo.current()
        trip = self.phone_ids[index] if 0 <= index < len(self.phone_ids) else None
        args = phone_export_args(self.place_var.get(), trip)
        self.worker_running = True
        self.set_buttons_enabled(False)
        threading.Thread(target=self.run_phone_export, args=(args,), daemon=True).start()

    def run_phone_export(self, args: list[str]) -> None:
        try:
            self.set_status("Eksportuje KMZ na telefon...")
            ok = self.run_command(
                [str(PYTHON_EXE), str(REPO_ROOT / "scripts" / "eksport_telefon.py"), *args], cwd=REPO_ROOT)
            if ok:
                self.log("Zsynchronizuj ten folder z Dyskiem Google / OneDrive i otworz plik w Locus Map / Guru Maps "
                         "(docs/TELEFON.md).")
                self.set_status("Eksport na telefon zakonczony.")
            else:
                self.set_status("Eksport na telefon sie nie powiodl - zobacz log.")
        finally:
            self.worker_running = False
            self.set_buttons_enabled(True)

    def run_command(self, cmd: list[str], cwd: Path) -> bool:
        self.log(f"$ {' '.join(cmd)}")
        try:
            process = subprocess.Popen(
                cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW, **child_process_kwargs(),
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
            # Plan 2.1: bez zapisanej migawki nie da sie pozniej ocenic rankingu z dnia wyjazdu.
            self.log("Przypomnienie: zapisz migawke (Zapisz do listy), jesli jedziesz dzis do lasu.")
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
        lan = self.lan_requested
        ip = lan_ip() if lan else None
        if server_is_up():
            self.log("Serwer juz dziala.")
            if lan and ip and not server_is_up(f"http://{ip}:{DEV_PORT}"):
                self.log("Uwaga: serwer dziala tylko lokalnie. Kliknij 'Zatrzymaj serwer' (albo zamknij "
                         "proces Vite, jesli byl uruchomiony poza launcherem) i uruchom ponownie.")
        else:
            self.set_status("Startuje serwer frontendu...")
            script = "dev:lan" if lan else "dev"
            self.log(f"$ npm.cmd run {script}")
            try:
                self.dev_process = subprocess.Popen(
                    ["npm.cmd", "run", script], cwd=str(FRONTEND_DIR),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW, **child_process_kwargs(),
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
        if lan:
            if ip:
                self.log(f"Adres w sieci lokalnej: http://{ip}:{DEV_PORT}  (bez hasla - tylko zaufana siec).")
                self.log("Gdy inny komputer sie nie laczy: zezwol Node.js w Zaporze Windows dla sieci prywatnej.")
            else:
                self.log("Nie wykryto adresu w sieci lokalnej (brak polaczenia?).")
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
