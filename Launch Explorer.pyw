"""Open the locally installed real-data explorer without showing a terminal."""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import Tk, messagebox

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
BASE = "http://127.0.0.1:5174"


def fail(message: str) -> None:
    window = Tk()
    window.withdraw()
    messagebox.showerror("Earthquake Cluster Explorer", message, parent=window)
    window.destroy()


def viewer_ready() -> bool:
    try:
        with urllib.request.urlopen(BASE + "/local-data/events.json", timeout=1) as response:
            document = json.load(response)
        return document.get("schema") == "quake-events/1" and document.get("provenance", {}).get("dataset_kind") == "real"
    except (OSError, ValueError, AttributeError):
        return False


def port_free() -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", 5174)) != 0


def main() -> None:
    if not (ROOT / "data/derived/events.json").is_file() or not (ROOT / "data/derived/analysis.json").is_file():
        fail("The local analysis files are missing. Ask Codex to rebuild the local earthquake data.")
        return
    if not viewer_ready():
        if not port_free():
            fail("Port 5174 is already in use by another application. Close it and try again.")
            return
        node = shutil.which("node.exe")
        vite = WEB / "node_modules/vite/bin/vite.js"
        if not node or not vite.is_file():
            fail("The local viewer dependencies are missing. Ask Codex to restore the project setup.")
            return
        try:
            process = subprocess.Popen(
                [node, str(vite), "--mode", "local-data", "--host", "127.0.0.1", "--port", "5174", "--strictPort"],
                cwd=WEB,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            fail("The local viewer could not start. Ask Codex to check the project setup.")
            return
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not viewer_ready() and process.poll() is None:
            time.sleep(0.25)
        if not viewer_ready():
            if process.poll() is None:
                process.terminate()
            fail("The local viewer did not start. Ask Codex to check the project setup.")
            return
    if not webbrowser.open(BASE + "/?data=local"):
        fail("The viewer is running, but your browser could not be opened.")


if __name__ == "__main__":
    main()
