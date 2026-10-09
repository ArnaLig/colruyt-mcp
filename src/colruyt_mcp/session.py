"""Browser-backed session: the user logs in by hand in a plain Edge, we only read cookies.

Imperva blacklists automated browsers (Playwright's launch sets navigator.webdriver), so Edge
is started as an ordinary process and CDP is attached only once, at the end, to read cookies.
Credentials are never read, typed or stored.
"""
import json
import re
import socket
import subprocess
import time
from pathlib import Path

import httpx

from . import config

COLRUYT_DOMAINS = ("colruyt.be", "collectandgo.be", "colruytgroup.com", "myxtra.be", "dcsecosystem.be")
# Only session cookies are replayed. In particular never send `reese84`: the browser renews it
# every ~10 min; a stale one makes Imperva answer 405, while no anti-bot cookie at all is accepted.
SESSION_COOKIE = re.compile(r"^(clpbff_session|JSESSIONID|WC_.+|COL_.+|APP_C_LANGUAGE|colruytlanguage)$")


class CookieStore:
    """Cookies exported from the Edge profile, persisted as JSON (Playwright cookie format)."""

    def __init__(self, path: Path = config.COOKIES_FILE):
        self.path = path

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, cookies: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        keep = [c for c in cookies if any(c["domain"].lstrip(".").endswith(d) for d in COLRUYT_DOMAINS)]
        self.path.write_text(json.dumps(keep, indent=1), encoding="utf-8")

    def to_jar(self) -> httpx.Cookies:
        jar = httpx.Cookies()
        for c in self.load():
            if not SESSION_COOKIE.match(c["name"]):
                continue
            jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
        return jar

    def update_from_jar(self, jar: httpx.Cookies) -> None:
        """Merge cookies the servers rotated during API calls back into the file."""
        current = {(c["name"], c["domain"], c.get("path", "/")): c for c in self.load()}
        changed = False
        for ck in jar.jar:
            if not SESSION_COOKIE.match(ck.name):
                continue
            key = (ck.name, ck.domain, ck.path)
            old = current.get(key)
            if old is None or old["value"] != ck.value:
                current[key] = {
                    "name": ck.name, "value": ck.value, "domain": ck.domain, "path": ck.path,
                    "expires": ck.expires or -1, "httpOnly": bool(ck.has_nonstandard_attr("HttpOnly")),
                    "secure": ck.secure, "sameSite": "Lax",
                }
                changed = True
        if changed:
            self.save(list(current.values()))

    def summary(self) -> dict:
        names = {c["name"] for c in self.load()}
        return {
            "file": str(self.path),
            "colruyt_session": "clpbff_session" in names,
            "cogo_session": "JSESSIONID" in names and any(n.startswith("WC_AUTHENTICATION_") for n in names),
            "updated": time.strftime("%Y-%m-%d %H:%M", time.localtime(self.path.stat().st_mtime))
            if self.path.exists() else None,
        }


def _edge_path() -> str:
    for p in config.EDGE_CANDIDATES:
        if p and Path(p).exists():
            return p
    raise RuntimeError("Microsoft Edge introuvable (définissez COLRUYT_MCP_BROWSER).")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch_edge(urls: list[str], port: int, minimized: bool = False) -> subprocess.Popen:
    config.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        _edge_path(),
        f"--user-data-dir={config.PROFILE_DIR}",
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        "--no-first-run",
        "--restore-last-session",
        "--new-window",
    ]
    if minimized:
        args.append("--start-minimized")
    return subprocess.Popen(args + urls)


def read_cookies_over_cdp(port: int) -> list[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        cookies = browser.contexts[0].cookies()
        browser.close()  # only disconnects
    return cookies


def interactive_login(store: CookieStore) -> dict:
    """CLI flow: open both login pages, the user logs in, presses Enter, cookies are saved."""
    port = _free_port()
    proc = launch_edge([config.CLP_LOGIN, config.COGO_LOGIN], port)
    print("Edge est ouvert sur les pages de connexion colruyt.be et Collect&Go.")
    print("Connectez-vous dans les deux onglets (cochez « rester connecté » si proposé).")
    input("Quand les deux sites affichent votre compte, appuyez sur Entrée… ")
    store.save(read_cookies_over_cdp(port))
    proc.terminate()
    return store.summary()


def silent_refresh(store: CookieStore, wait_s: int = 25) -> dict:
    """Best effort: reopen the profile on both login URLs; the B2C SSO cookie (if still valid)
    logs in without user action. Nothing is attached while pages load."""
    port = _free_port()
    proc = launch_edge([config.CLP_LOGIN, config.COGO_LOGIN], port, minimized=True)
    try:
        time.sleep(wait_s)
        store.save(read_cookies_over_cdp(port))
    finally:
        proc.terminate()
    return store.summary()
