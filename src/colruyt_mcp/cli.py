"""colruyt-mcp CLI: `serve` (default, stdio MCP), `login`, `refresh`, `status`."""
import argparse
import asyncio
import json

from .session import CookieStore, interactive_login, silent_refresh


def main() -> None:
    parser = argparse.ArgumentParser(prog="colruyt-mcp")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "login", "refresh", "status"])
    parser.add_argument("--site", choices=["cogo", "colruyt", "all"], default="all",
                        help="refresh : site(s) à reconnecter (défaut : all)")
    parser.add_argument("--browser", help="login: edge | chrome | chromium | chemin de l'exécutable "
                                          "(par défaut : celui du dernier login, sinon détection automatique)")
    args = parser.parse_args()
    cmd = args.command
    store = CookieStore()
    if cmd == "serve":
        from .server import main as serve
        serve()
    elif cmd == "login":
        print(json.dumps(interactive_login(store, args.browser), indent=1, ensure_ascii=False))
    elif cmd == "refresh":
        sites = ("colruyt", "cogo") if args.site == "all" else (args.site,)
        print(json.dumps(silent_refresh(store, sites), indent=1, ensure_ascii=False))
    else:
        from .client import ColruytClient
        from .logic import Service

        async def status():
            svc = Service(ColruytClient(store))
            try:
                return await svc.session_status()
            finally:
                await svc.c.aclose()

        print(json.dumps(asyncio.run(status()), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
