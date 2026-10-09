# colruyt-mcp

*Français : [README.fr.md](README.fr.md)*

> **Unofficial, personal-use project.** Not affiliated with, endorsed by or supported by Colruyt
> Group, Xtra or Collect&Go. Read the [disclaimer](#disclaimer) before using it.

A local (stdio) [Model Context Protocol](https://modelcontextprotocol.io) server that lets an AI
assistant help you with your own Colruyt account: search the catalogue, browse Colruyt recipes
(including your favourites), turn recipes into product lists, manage your **Xtra** shopping list
(colruyt.be) and fill your **Collect&Go** cart, pick-up point and time slot. It also tracks the
weekly "free service fee" brand actions.

**It never places or pays an order.** Checkout, payment and cancellation endpoints are blocked in
the client; you always finish the order yourself on collectandgo.be.

## How it works

- Runs on your machine, for your account only. Nothing is sent anywhere else.
- **No credentials are handled.** You log in yourself, in a regular Microsoft Edge window with a
  dedicated profile (SMS second factor included). The tool then reads the session cookies of
  that profile and replays them, the way your browser does.
- It does not bypass the sites' bot protection. Automated browsers get blocked, so login is
  manual by design. If the sites block a request, the tool stops and reports it.
- No catalogue or recipe data is stored. Responses are used for the current request only, apart
  from short-lived in-memory caches.

## Requirements

- Windows with Microsoft Edge
- [uv](https://docs.astral.sh/uv/)
- A Colruyt Xtra account (Belgium)

```bash
uv sync
```

## Log in

```bash
uv run colruyt-mcp login
```

1. Edge opens on the colruyt.be and Collect&Go login pages.
2. Log in on both tabs. Tick "stay signed in" if it is offered.
3. Press Enter in the terminal.

Other commands:

```bash
uv run colruyt-mcp status
```

```bash
uv run colruyt-mcp refresh
```

`status` checks both sessions. `refresh` tries a silent re-login: it briefly opens Edge and reuses
the Azure B2C single sign-on if it is still valid.

Personal files live outside the repository, in `~/.colruyt-mcp/` (override with
`COLRUYT_MCP_HOME`): `cookies.json` and `edge-profile/`. Keep them private: they give access to
your account.

## Connect it to Claude

**Claude Desktop.** In Settings → Developer → Edit Config, add this under `mcpServers`, then quit
Claude completely and restart it:

```json
"colruyt": {
  "command": "C:\\Users\\<you>\\.local\\bin\\uv.exe",
  "args": ["run", "--directory", "C:\\path\\to\\colruyt-mcp", "colruyt-mcp"]
}
```

**Claude Code:**

```bash
claude mcp add colruyt -- uv run --directory C:\path\to\colruyt-mcp colruyt-mcp
```

## Tools

| Area | Tools |
|---|---|
| Session | `session_status`, `refresh_session` |
| Catalogue | `search_products`, `get_products`, `get_purchase_history` (last ticket, most bought, Collect&Go history) |
| Recipes | `list_favorite_recipes`, `search_recipes`, `get_recipe`, `map_recipes_to_products` |
| Xtra list | `get_xtra_list`, `add_to_xtra_list`, `update_xtra_list_item`, `remove_xtra_list_item` |
| Collect&Go cart | `get_cart`, `add_to_cart`, `update_cart_item` (quantity 0 removes the line) |
| Pick-up | `list_pickup_points`, `set_pickup_point`, `get_pickup_slots`, `reserve_pickup_slot` |
| Service fee | `list_service_fee_actions`, `service_fee_action_details` (50 % / 100 % tiers), `service_fee_progress` |

Write tools act directly on your account. The server tells the assistant to re-read the cart or
list regularly to check the result.

Default language is French (`COLRUYT_MCP_LANG=nl` for Dutch).

## Development

```bash
uv run pytest
```

Tests are offline. `scripts/` holds the discovery tooling (HAR inspection, session replay);
captures go to `captures/`, which git ignores.

## Disclaimer

**Read this before use.** This summary is not legal advice.

**Unofficial.** This project is an independent, non-commercial, personal tool. It is not
affiliated with, authorised, endorsed or supported by Colruyt Group, Etn. Fr. Colruyt NV, Colruyt
Food Retail NV, Bio-Planet NV, Xtra or Collect&Go. The APIs it uses are undocumented internal
interfaces. They may change or disappear at any time, and the tool may break or misbehave as a
result.

**Terms of use apply to you.** Using these sites, with or without this tool, is governed by
Colruyt Group's terms. The versions read on 9 October 2026 contain, among others:

- **Website terms of use** (Colruyt Group sites, version 06/2019), art. 4–5: extracting or reusing
  the site's content, including screen scraping, is prohibited. Under database law, a lawful user
  may still extract **non-substantial** parts for normal use. Substantial or **systematic**
  extraction, and use that harms the database owner, are not allowed.
- **Xtra Digital general terms** (v0202609210), art. 17: the digital channels (software, source
  code, data, structure…) are protected. Reproduction, publication, adaptation or use is
  prohibited unless expressly authorised by Xtra, and so is storing their content in a database.
  Art. 14: Xtra may suspend the service, without notice, in case of (suspected) abuse,
  unauthorised use or a threat to system security.
- **Collect&Go general terms** (V0202601270): service for reasonable private, household use; the
  account may be blocked in case of abuse.
- The Collect&Go `robots.txt` disallows automated access to booking, slot, checkout and account
  pages. The colruyt.be `robots.txt` asks crawlers for a 5-second crawl delay.

None of these documents explicitly addresses personal automation tools or API clients. Their
wording is broad, though, and **this tool may not be considered an authorised use.** Possible
consequences include the suspension of your Xtra or Collect&Go account. Before using the tool,
read the current terms yourself. They are linked from the footers of colruyt.be, collectandgo.be
and monxtra.be.

**Use responsibly.** If you use the tool:

- use it only with **your own** account, for personal, household shopping;
- keep request volumes comparable to manual use. Do not scrape the catalogue, prices, recipes or
  promotions, and do not build datasets from them;
- do not redistribute Colruyt content (texts, images, recipes, product data);
- do not use it to circumvent bot protection, access controls or rate limits.

**No warranty.** The software is provided "as is", without warranty of any kind. You are solely
responsible for what it does on your account. That includes products added to your cart or
list, slots reserved, prices and promotions, which can be wrong or out of date. Always review your
cart on collectandgo.be before ordering. The author accepts no liability for any damage, loss,
account suspension or order error.

**Trademarks.** Colruyt, Xtra, Collect&Go, Bio-Planet, Boni and other names are trademarks of their
respective owners. They are used here only to describe what the software interoperates with.

If you represent Colruyt Group and have concerns about this project, please open an issue. It will
be addressed promptly, including taking the repository down if requested.

## License

[MIT](LICENSE). The licence covers this code only, not any Colruyt content or service.
