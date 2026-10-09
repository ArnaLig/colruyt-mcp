"""Find and drive a Chromium-family browser (Edge, Chrome, Chromium) on Windows or Linux.

The browser is started as an ordinary process with a dedicated profile (never through Playwright's
launcher, which Imperva blacklists). It only exposes a local DevTools port, used once to read
cookies after the user has logged in.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import config

FAMILIES = ("edge", "chrome", "chromium")


def _win_candidates() -> dict[str, list[str]]:
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    return {
        "edge": [rf"{pf86}\Microsoft\Edge\Application\msedge.exe", rf"{pf}\Microsoft\Edge\Application\msedge.exe"],
        "chrome": [rf"{pf}\Google\Chrome\Application\chrome.exe", rf"{pf86}\Google\Chrome\Application\chrome.exe",
                   rf"{local}\Google\Chrome\Application\chrome.exe"],
        "chromium": [rf"{local}\Chromium\Application\chrome.exe"],
    }


LINUX_COMMANDS = {
    "chrome": ["google-chrome", "google-chrome-stable"],
    "chromium": ["chromium", "chromium-browser"],
    "edge": ["microsoft-edge", "microsoft-edge-stable"],
}
# Without an explicit choice: keep Edge first on Windows (existing profiles), Chrome first on Linux.
DEFAULT_ORDER = {"win32": ["edge", "chrome", "chromium"], "linux": ["chrome", "chromium", "edge"]}


@dataclass
class Browser:
    family: str
    path: str

    @property
    def profile_dir(self) -> Path:
        return config.HOME / f"{self.family}-profile"


def _locate(family: str, platform: str) -> str | None:
    if platform == "win32":
        return next((p for p in _win_candidates()[family] if Path(p).exists()), None)
    return next((found for cmd in LINUX_COMMANDS[family] if (found := shutil.which(cmd))), None)


def _family_of(path: str) -> str:
    name = Path(path).name.lower()
    if "edge" in name:
        return "edge"
    return "chromium" if "chromium" in name or "chromium" in path.lower() else "chrome"


def find_browser(preference: str | None = None, platform: str = sys.platform) -> Browser:
    """preference: 'edge' | 'chrome' | 'chromium' | a path to the executable | None (saved choice, then auto)."""
    platform = "win32" if platform.startswith("win") else "linux"
    pref = (preference or os.environ.get("COLRUYT_MCP_BROWSER") or saved_browser() or "").strip()
    if pref and pref.lower() not in FAMILIES:
        if not (Path(pref).exists() or shutil.which(pref)):
            raise RuntimeError(f"Navigateur introuvable : {pref}")
        path = pref if Path(pref).exists() else shutil.which(pref)
        return Browser(_family_of(path), path)
    for family in ([pref.lower()] if pref else DEFAULT_ORDER[platform]):
        if path := _locate(family, platform):
            return Browser(family, path)
    wanted = pref or " / ".join(DEFAULT_ORDER[platform])
    raise RuntimeError(f"Aucun navigateur trouvé ({wanted}). Installez Chrome ou Edge, ou définissez "
                       "COLRUYT_MCP_BROWSER avec le chemin de l'exécutable.")


# ------------------------------------------------------------------ remembered choice

def saved_browser() -> str | None:
    try:
        return json.loads(config.BROWSER_FILE.read_text(encoding="utf-8")).get("path")
    except (OSError, ValueError):
        return None


def saved_user_agent() -> str | None:
    try:
        return json.loads(config.BROWSER_FILE.read_text(encoding="utf-8")).get("user_agent")
    except (OSError, ValueError):
        return None


def remember(browser: Browser, user_agent: str | None) -> None:
    config.BROWSER_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.BROWSER_FILE.write_text(json.dumps({"family": browser.family, "path": browser.path,
                                               "user_agent": user_agent}, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ process & DevTools

def launch(browser: Browser, urls: list[str], port: int, minimized: bool = False) -> subprocess.Popen:
    browser.profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        browser.path,
        f"--user-data-dir={browser.profile_dir}",
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        "--no-first-run",
        "--no-default-browser-check",
        "--restore-last-session",
        "--new-window",
    ]
    if minimized:
        args.append("--start-minimized")
    return subprocess.Popen(args + urls, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def devtools_version(port: int, timeout_s: float = 20) -> dict:
    """Wait for the DevTools endpoint. Plain HTTP on localhost: nothing is attached to any page."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                return json.load(r)
        except OSError:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    "Le navigateur n'a pas ouvert son port de débogage local. Une fenêtre utilise sans doute "
                    "déjà le profil colruyt-mcp : fermez-la puis recommencez.") from None
            time.sleep(0.5)


def read_cookies_and_close(port: int, close: bool = True) -> list[dict]:
    """Attach once over CDP, read all cookies, then close the browser gracefully (cookies flushed)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        cookies = browser.contexts[0].cookies()
        if close:
            try:
                browser.new_browser_cdp_session().send("Browser.close")
            except Exception:  # already closing
                pass
        browser.close()  # disconnects
    return cookies
