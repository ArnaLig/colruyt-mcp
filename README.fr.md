# colruyt-mcp

*English: [README.md](README.md)*

> **Projet non officiel, à usage personnel.** Sans lien avec Colruyt Group, Xtra ou Collect&Go.
> Lisez l'[avertissement](#avertissement) avant toute utilisation.

Serveur MCP local (stdio) pour l'écosystème Colruyt : catalogue, recettes (dont favoris),
liste de courses **Xtra** (colruyt.be) et panier **Collect&Go**, avec point et créneau
d'enlèvement et actions « frais de service offerts ».

**Le MCP ne valide jamais de commande ni de paiement** : les chemins `checkout`, paiement et
annulation sont bloqués dans le client. Vous terminez vous-même sur collectandgo.be.


## Installation

Prérequis : Windows ou Linux, avec Google Chrome, Microsoft Edge ou Chromium, et [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Connexion

Le site bloque les navigateurs automatisés. La connexion se fait donc dans un navigateur **normal**,
avec un profil dédié. Le MCP ne voit jamais vos identifiants : il lit seulement les cookies une
fois que vous êtes connecté.

```bash
uv run colruyt-mcp login
```

1. Le navigateur s'ouvre sur les pages de connexion colruyt.be et Collect&Go.
2. Connectez-vous dans les deux onglets (code SMS). Cochez « rester connecté » si c'est proposé.
3. Appuyez sur Entrée dans le terminal.

Autres commandes :

```bash
uv run colruyt-mcp status
```

```bash
uv run colruyt-mcp refresh
```

`status` vérifie les deux sessions. `refresh` tente une reconnexion silencieuse : il rouvre
brièvement le navigateur du login et réutilise la connexion unique (SSO) Azure B2C si elle est encore valide.

Fichiers personnels (hors dépôt) dans `~/.colruyt-mcp/`, ou `COLRUYT_MCP_HOME` :
`cookies.json`, `browser.json` et `<navigateur>-profile/`.

### Choix du navigateur

Sans précision, l'outil cherche Edge, puis Chrome, puis Chromium sous Windows. Sous Linux, il
cherche `google-chrome`, puis `chromium`, puis `microsoft-edge`. Pour en imposer un :

```bash
uv run colruyt-mcp login --browser chrome
```

`--browser` accepte `chrome`, `edge`, `chromium` ou le chemin de l'exécutable. La variable
d'environnement `COLRUYT_MCP_BROWSER` fait la même chose. Le navigateur utilisé au login est
mémorisé : `refresh` le réutilise, avec le même profil.

- Chaque navigateur a son propre profil : changer de navigateur impose de se reconnecter.
- Fermez toute fenêtre qui utilise déjà le profil colruyt-mcp avant `login` ou `refresh`.
- Linux avec Chromium en snap : le confinement snap masque les dossiers cachés du répertoire
  personnel. Définissez `COLRUYT_MCP_HOME` sur un dossier non caché (par exemple
  `~/colruyt-mcp-data`), ou utilisez Google Chrome en `.deb`.

### Durée des sessions

La session Collect&Go expire après une période d'inactivité (environ une demi-heure lors de nos
tests). La session colruyt.be dure bien plus longtemps. Quand une session a expiré, l'assistant
appelle `refresh_session` : le navigateur se rouvre quelques secondes et se reconnecte par
l'authentification unique, sans nouveau code SMS, tant que cette authentification unique est
encore valide.

## Brancher le MCP

Claude Code :

```bash
claude mcp add colruyt -- uv run --directory C:\chemin\vers\colruyt-mcp colruyt-mcp
```

Claude Desktop (`claude_desktop_config.json`). Sous Linux, mettez le chemin complet de `uv`
(par exemple `/home/<vous>/.local/bin/uv`) et un chemin Linux pour `--directory` :

```json
{
  "mcpServers": {
    "colruyt": {
      "command": "C:\\Users\\<vous>\\.local\\bin\\uv.exe",
      "args": ["run", "--directory", "C:\\chemin\\vers\\colruyt-mcp", "colruyt-mcp"]
    }
  }
}
```

## Outils

| Domaine | Outils |
|---|---|
| Session | `session_status`, `refresh_session` |
| Catalogue | `search_products`, `get_products`, `get_purchase_history` (dernières courses, plus achetés, historique C&G) |
| Recettes | `list_favorite_recipes`, `search_recipes`, `get_recipe`, `map_recipes_to_products` |
| Liste Xtra | `get_xtra_list`, `add_to_xtra_list`, `update_xtra_list_item`, `remove_xtra_list_item` |
| Panier C&G | `get_cart`, `add_to_cart`, `update_cart_item` (quantité 0 = supprimer) |
| Enlèvement | `list_pickup_points`, `set_pickup_point`, `get_pickup_slots`, `reserve_pickup_slot` |
| Frais de service | `list_service_fee_actions`, `service_fee_action_details` (paliers 50 % / 100 %), `service_fee_progress` |

Langue par défaut : `fr` (`COLRUYT_MCP_LANG=nl` pour le néerlandais).

## Développement

```bash
uv run pytest
```

Scripts de découverte (phase 1) dans `scripts/`. Les captures (HAR, cookies) vont dans
`captures/`, qui est ignoré par git.

## Avertissement

Ce résumé n'est pas un avis juridique ; la version complète, en anglais, est dans
[README.md](README.md#disclaimer).

- **Non officiel** : outil indépendant, non commercial. Il s'appuie sur des API internes non
  documentées, qui peuvent changer à tout moment.
- **Conditions d'utilisation** (lues le 9 octobre 2026) :
  - conditions des sites web Colruyt Group (06/2019), art. 4–5 : l'extraction ou la
    réutilisation du contenu est interdite, capture d'écran comprise. Seule est permise
    l'extraction de parties non substantielles, pour une exploitation normale ;
  - conditions Xtra Digital, art. 17 : reproduction, publication, adaptation ou utilisation
    des canaux numériques interdites sauf autorisation expresse, et stockage de leur contenu dans
    une base de données interdit ;
  - conditions Xtra Digital, art. 14 : suspension possible du service, sans préavis, en cas d'abus
    ou d'utilisation non autorisée.

  Ces textes ne parlent pas explicitement des outils d'automatisation personnels, mais ils sont
  larges : **cet usage pourrait ne pas être considéré comme autorisé**, et votre compte pourrait
  être suspendu. Lisez les conditions en vigueur avant d'utiliser l'outil.
- **Usage responsable** : uniquement votre propre compte, pour vos courses personnelles, avec
  des volumes comparables à un usage manuel. Pas d'aspiration du catalogue, des recettes ou des
  promos, pas de redistribution de contenu, pas de contournement des protections anti-bot.
- **Aucune garantie** : vous êtes seul responsable de ce que l'outil fait sur votre compte.
  Vérifiez toujours votre panier sur collectandgo.be avant de commander.
- **Marques** : Colruyt, Xtra, Collect&Go, Bio-Planet, Boni… appartiennent à leurs propriétaires.

## Licence

[MIT](LICENSE) — couvre uniquement ce code, pas les contenus ou services Colruyt.
