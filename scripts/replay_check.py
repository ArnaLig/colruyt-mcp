"""Phase-1 check: can browser cookies be reused outside the browser (httpx)?

READ-ONLY: only GET requests. Prints status codes and sizes, never values.
Each call is tried with several cookie subsets to see which cookie is required.

Usage: uv run python scripts/replay_check.py [captures/session/cookies-XXXX.json]
"""
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0")
CLP_BFF = "https://apix.colruyt.be/gateway/emec.colruyt.bffsvc"
COGO_GW = "https://apip.collectandgo.be/gateway/ecomfoodb2c.eshop"


def load_cookies(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def cookie_header(cookies, host, keep=None, drop=()):
    out = []
    for c in cookies:
        d = c["domain"].lstrip(".")
        if not (host == d or host.endswith("." + d)):
            continue
        if keep is not None and not any(c["name"].startswith(k) for k in keep):
            continue
        if any(c["name"].startswith(k) for k in drop):
            continue
        out.append(f"{c['name']}={c['value']}")
    return "; ".join(out)


def clp_apikey(client) -> str:
    page = client.get("https://www.colruyt.be/fr", headers={"User-Agent": UA}).text
    raw = re.search(r'data-endpoints="([^"]+)"', page).group(1)
    return re.search(r"X-CG-APIKey:\s*([\w-]+)", html.unescape(raw)).group(1)


def summarise(r: httpx.Response) -> str:
    body = r.text
    info = f"{r.status_code} {len(body)}o"
    try:
        j = r.json()
        if isinstance(j, dict):
            info += " keys=" + ",".join(list(j)[:6])
        elif isinstance(j, list):
            info += f" list[{len(j)}]"
    except ValueError:
        if "<html" in body[:500].lower():
            t = re.search(r"<title>(.*?)</title>", body, re.S | re.I)
            info += f" html title={t.group(1).strip()[:60]!r}" if t else " html"
    return info


def main() -> None:
    files = sorted((ROOT / "captures" / "session").glob("cookies-2*.json"))
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else files[-1]
    cookies = load_cookies(path)
    age_min = (time.time() - path.stat().st_mtime) / 60
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z — cookies {path.name} (exportés il y a {age_min:.0f} min)\n")

    variants = {
        "tous cookies": dict(),
        "sans reese84": dict(drop=("reese84",)),
        "session seule": dict(keep=("clpbff_session", "JSESSIONID", "WC_")),
        "aucun cookie": dict(keep=()),
    }

    with httpx.Client(timeout=20, follow_redirects=False, http2=False) as client:
        key = clp_apikey(client)  # public key, re-read from the anonymous home page
        clp_calls = [
            ("auth/check", f"{CLP_BFF}/auth/check", {}),
            ("preferredStore", f"{CLP_BFF}/cg/preferredStore", {}),
            ("get-favorite-recipes", f"{CLP_BFF}/cg/get-favorite-recipes", {}),
            ("latest-shopping-list", f"{CLP_BFF}/cg/latest-shopping-list",
             {"limit": 5, "offset": 0, "lang": "fr", "prs": "true"}),
        ]
        print("== colruyt.be BFF (apix) ==")
        for name, url, params in clp_calls:
            for vname, v in variants.items():
                h = {"User-Agent": UA, "X-CG-APIKey": key, "Accept": "application/json",
                     "Origin": "https://www.colruyt.be", "Referer": "https://www.colruyt.be/"}
                ck = cookie_header(cookies, "apix.colruyt.be", **v)
                if ck:
                    h["Cookie"] = ck
                r = client.get(url, params=params, headers=h)
                print(f"  {name:22} [{vname:13}] {summarise(r)}")

        print("\n== Collect&Go ==")
        for vname, v in variants.items():
            h = {"User-Agent": UA, "Accept": "text/html"}
            ck = cookie_header(cookies, "www.collectandgo.be", **v)
            if ck:
                h["Cookie"] = ck
            r = client.get("https://www.collectandgo.be/fr/home", headers=h)
            logged = re.search(r'"loggedIn"\s*:\s*(\w+)', r.text)
            print(f"  page /fr/home        [{vname:13}] {r.status_code} loggedIn={logged.group(1) if logged else '?'}"
                  + (f" -> {r.headers.get('location', '')[:60]}" if r.is_redirect else ""))

        h = {"User-Agent": UA, "Accept": "text/html", "Cookie": cookie_header(cookies, "www.collectandgo.be")}
        page = client.get("https://www.collectandgo.be/fr/home", headers=h).text
        tok = re.search(r'"WCAuthToken"\s*:\s*\'([^\']*)\'', page)
        gwkey = re.search(r'"apiGatewayKey"\s*:\s*\'([^\']*)\'', page)
        print(f"  WCAuthToken trouvé : {bool(tok and tok.group(1))} ; apiGatewayKey trouvée : {bool(gwkey)}")
        if not (tok and gwkey):
            return
        cogo_calls = [
            ("cart/@self", f"{COGO_GW}.wcscartsvcv2/v2/store/90004/cart/@self", {"langId": "-2"}),
            ("recipes/list-favourites", f"{COGO_GW}.wcsrecipesvc/v1/store/90004/recipes/list-favourites", {}),
        ]
        for name, url, params in cogo_calls:
            for vname, v in {**variants, "token sans cookie": dict(keep=())}.items():
                hh = {"User-Agent": UA, "Accept": "*/*", "Content-Type": "application/json",
                      "Origin": "https://www.collectandgo.be", "Referer": "https://www.collectandgo.be/",
                      "X-CG-APIKey": gwkey.group(1), "WCAuthToken": tok.group(1)}
                ck = cookie_header(cookies, "apip.collectandgo.be", **v)
                if ck:
                    hh["Cookie"] = ck
                r = client.get(url, params=params, headers=hh)
                print(f"  {name:22} [{vname:17}] {summarise(r)}")


if __name__ == "__main__":
    main()
