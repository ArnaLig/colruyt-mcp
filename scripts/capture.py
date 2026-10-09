"""Open a plain (non-automated) Edge for manual browsing, then export its cookies.

Why not Playwright's launch: it adds --enable-automation (navigator.webdriver = true)
and keeps a CDP session attached while browsing; Imperva's reese84 detects that and
blacklists the session. Here Edge is started as an ordinary process; nothing is
attached while the user browses.

- Dedicated profile in .profile-edge/ (gitignored). The script never touches credentials.
- HAR: exported by the user from Edge DevTools (Network > Export HAR *with sensitive
  data*) into captures/har/.
- Cookies: only after the user presses Enter, the script attaches once over CDP
  (local port) to read cookies, writes them to captures/session/ (gitignored), detaches.
  Closing the Edge window early is harmless: cookies are then read from the next run.

Usage: uv run python scripts/capture.py
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / ".profile-edge"
SESSION_DIR = ROOT / "captures" / "session"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
PORT = 9333
START_URLS = ["https://www.colruyt.be/fr", "https://www.collectandgo.be/fr"]
DOMAINS = ("colruyt", "collectandgo", "xtra", "dcsecosystem")


def export_cookies(stamp: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        cookies = browser.contexts[0].cookies()
        browser.close()  # detaches only; Edge keeps running
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    (SESSION_DIR / f"cookies-{stamp}.json").write_text(json.dumps(cookies, indent=1), encoding="utf-8")
    # Value-free summary, safe to read and to quote in docs.
    meta = [
        {k: c[k] for k in ("name", "domain", "path", "expires", "httpOnly", "secure", "sameSite")}
        | {"value_len": len(c["value"])}
        for c in cookies
        if any(d in c["domain"] for d in DOMAINS)
    ]
    (SESSION_DIR / f"cookies-meta-{stamp}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"Cookies exportés : {len(cookies)} ({len(meta)} pour les domaines Colruyt) -> captures/session/")


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    subprocess.Popen([
        str(EDGE),
        f"--user-data-dir={PROFILE}",
        f"--remote-debugging-port={PORT}",
        "--remote-debugging-address=127.0.0.1",
        "--no-first-run",
        "--auto-open-devtools-for-tabs",
        "--new-window",
        *START_URLS,
    ])
    print("Edge ouvert (profil .profile-edge, sans automatisation).")
    print("1. Ouvrez les DevTools (F12) > onglet Réseau AVANT de naviguer, cochez « Conserver le journal ».")
    print("2. Connectez-vous vous-même puis faites le parcours.")
    print("3. Exportez le HAR (icône ⤓ > « avec données sensibles ») dans captures\\har\\.")
    print("4. Laissez Edge ouvert et appuyez sur Entrée ici pour exporter les cookies.")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
    try:
        export_cookies(stamp)
    except Exception as exc:  # Edge closed, port unavailable…
        print(f"Export des cookies impossible ({exc}). Relancez le script : le profil garde la session.")


if __name__ == "__main__":
    main()
