"""Browser-backed session: the user logs in by hand in a regular browser (Edge, Chrome or
Chromium, see browser.py); we only read cookies afterwards. Credentials are never read, typed
or stored.
"""
import json
import re
import socket
import subprocess
import time
from pathlib import Path

import httpx

from . import browser, config

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
        cookies = self.load()
        names = {c["name"] for c in cookies}
        clp = next((c for c in cookies if c["name"] == "clpbff_session"), None)
        expires = clp.get("expires", -1) if clp else -1
        return {
            "file": str(self.path),
            "colruyt_session": clp is not None,
            # The colruyt.be session cookie is persistent (about 60 days): no browser needed until then.
            "colruyt_expires": time.strftime("%Y-%m-%d", time.localtime(expires)) if expires > 0 else None,
            "colruyt_days_left": max(0, int((expires - time.time()) // 86400)) if expires > 0 else None,
            "cogo_session": "JSESSIONID" in names and any(n.startswith("WC_AUTHENTICATION_") for n in names),
            "updated": time.strftime("%Y-%m-%d %H:%M", time.localtime(self.path.stat().st_mtime))
            if self.path.exists() else None,
        }


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stop(proc: subprocess.Popen) -> None:
    try:
        proc.wait(timeout=5)  # Browser.close already sent: usually exits by itself
    except subprocess.TimeoutExpired:
        proc.terminate()


def interactive_login(store: CookieStore, preference: str | None = None) -> dict:
    """CLI flow: open both login pages, the user logs in, presses Enter, cookies are saved."""
    b = browser.find_browser(preference)
    port = _free_port()
    proc = browser.launch(b, [config.CLP_LOGIN, config.COGO_LOGIN], port)
    try:
        user_agent = browser.devtools_version(port).get("User-Agent")
        print(f"{b.family.title()} est ouvert ({b.path}) sur les pages de connexion colruyt.be et Collect&Go.")
        print("Connectez-vous dans les deux onglets (cochez « rester connecté » si proposé).")
        input("Quand les deux sites affichent votre compte, appuyez sur Entrée… ")
        store.save(browser.read_cookies_and_close(port))
        browser.remember(b, user_agent)
    finally:
        _stop(proc)
    return store.summary() | {"browser": b.family}


# Login URL to open, and where the tab lands once single sign-on has logged the user in.
REFRESH_TARGETS = {
    "colruyt": (config.CLP_LOGIN, "https://www.colruyt.be/"),
    "cogo": (config.COGO_LOGIN, "https://www.collectandgo.be/fr/home"),
}


def silent_refresh(store: CookieStore, sites: tuple[str, ...] = ("cogo",), timeout_s: float = 40) -> dict:
    """Best effort: reopen the browser profile used at login on the login page of `sites`; the B2C
    single sign-on cookie (if still valid) logs in without user action. Nothing is attached to the
    pages while they load: progress is read from the local DevTools tab list, then cookies are read
    once and the browser is closed."""
    b = browser.find_browser()
    port = _free_port()
    proc = browser.launch(b, [REFRESH_TARGETS[s][0] for s in sites], port, minimized=True)
    try:
        user_agent = browser.devtools_version(port).get("User-Agent")
        landed = browser.wait_for_tabs(port, {s: REFRESH_TARGETS[s] for s in sites}, timeout_s)
        store.save(browser.read_cookies_and_close(port))
        browser.remember(b, user_agent)
    finally:
        _stop(proc)
    return store.summary() | {"browser": b.family, "reconnected": landed,
                              "needs_manual_login": not all(landed.values())}
