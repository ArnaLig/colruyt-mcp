"""MCP server (stdio) exposing Colruyt Xtra / Collect&Go tools. Never places an order."""
import asyncio
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from .client import ColruytClient, ColruytError
from .logic import Service
from .session import CookieStore, silent_refresh

INSTRUCTIONS = """\
Outils Colruyt : catalogue, recettes (dont favoris), liste Xtra (colruyt.be) et panier Collect&Go.
- Le MCP ne valide JAMAIS de commande ni de paiement : l'utilisateur termine lui-même sur collectandgo.be.
- Identifiant produit commun : technical_article_number.
- Recette → produits : map_recipes_to_products classe les candidats (déjà achetés d'abord). Écartez
  les 'pantry_item' sauf demande contraire.
- Les écritures (liste, panier, point d'enlèvement, créneau) sont directes : relisez régulièrement
  get_cart / get_xtra_list pour vérifier le résultat, surtout après plusieurs ajouts.
- Frais de service : list_service_fee_actions / service_fee_progress. Si un seuil est proche,
  proposez les produits de l'action. Vérifiez service_fee_discount dans get_cart.
- Si une session est expirée : refresh_session ; si ça échoue, demandez à l'utilisateur de lancer
  `colruyt-mcp login` dans un terminal (connexion manuelle + SMS).
"""

mcp = MCPServer("colruyt", instructions=INSTRUCTIONS)
_state: dict = {}
READ = ToolAnnotations(read_only_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)
DELETE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=True)


def service() -> Service:
    if "svc" not in _state:
        _state["svc"] = Service(ColruytClient(CookieStore()))
    return _state["svc"]


async def run(coro):
    try:
        return await coro
    except ColruytError as exc:
        raise ToolError(str(exc)) from exc


class RecipeRequest(BaseModel):
    recipe_id: str
    servings: int = Field(4, ge=1, le=20)


class ListItem(BaseModel):
    technical_article_number: str | None = None
    description: str | None = Field(None, description="Texte libre si pas de produit précis")
    quantity: int = Field(1, ge=1, description="Entier (la liste Xtra refuse les décimales)")
    unit: Literal["P", "W"] = "P"


class CartItem(BaseModel):
    technical_article_number: str
    quantity: float = Field(1, gt=0, description="En unités choisies : pièces, packs, kg…")
    unit: Literal["P", "PA", "W", "PR"] | None = Field(None, description="Par défaut : 1re unité vendable")


# ------------------------------------------------------------------ session
@mcp.tool(annotations=READ)
async def session_status() -> dict:
    """État des sessions colruyt.be et Collect&Go."""
    return await run(service().session_status())


@mcp.tool(annotations=WRITE)
async def refresh_session() -> dict:
    """Tente une reconnexion silencieuse (profil Edge + SSO). Ouvre brièvement Edge."""
    svc = service()
    summary = await asyncio.to_thread(silent_refresh, svc.c.store)
    svc.c.reload_cookies()
    return {"cookies": summary, "status": await run(svc.session_status())}


# ------------------------------------------------------------------ catalogue
@mcp.tool(annotations=READ)
async def search_products(query: str, size: int = 10, only_promo: bool = False, only_bio: bool = False) -> dict:
    """Recherche dans le catalogue Colruyt (prix du magasin préféré). bought_before = déjà acheté."""
    return await run(service().search_products(query, size=size, inPromo=only_promo, isBio=only_bio))


@mcp.tool(annotations=READ)
async def get_products(technical_article_numbers: list[str]) -> list[dict]:
    """Fiches produits (prix colruyt.be + disponibilité, unités et promos Collect&Go)."""
    return await run(service().products(technical_article_numbers))


@mcp.tool(annotations=READ)
async def get_purchase_history(
    kind: Literal["last_ticket", "most_bought", "cogo_last_order", "cogo_top"] = "most_bought",
) -> list[dict]:
    """Listes techniques : dernières courses (last_ticket), achetés le plus souvent (most_bought),
    dernière commande C&G, habituels C&G. Lecture seule."""
    return await run(service().purchase_history(kind))


# ------------------------------------------------------------------ recettes
@mcp.tool(annotations=READ)
async def list_favorite_recipes(offset: int = 0, limit: int = 30) -> dict:
    """Recettes favorites (communes Xtra / Collect&Go)."""
    return await run(service().favorite_recipes(offset, limit))


@mcp.tool(annotations=READ)
async def search_recipes(text: str, limit: int = 10) -> list[dict]:
    """Recherche de recettes Colruyt par texte."""
    return await run(service().search_recipes(text, limit))


@mcp.tool(annotations=READ)
async def get_recipe(recipe_id: str) -> dict:
    """Détail d'une recette : ingrédients, étapes, portions."""
    return await run(service().recipe(recipe_id))


@mcp.tool(annotations=READ)
async def map_recipes_to_products(recipes: list[RecipeRequest], candidates: int = 3) -> dict:
    """Pour chaque ingrédient des recettes (au nombre de portions voulu), produits candidats classés,
    avec quantité nécessaire, prix et 'bought_before'."""
    return await run(service().map_recipes([r.model_dump() for r in recipes], candidates))


# ------------------------------------------------------------------ liste Xtra
@mcp.tool(annotations=READ)
async def get_xtra_list(include_completed: bool = False) -> dict:
    """Liste de courses Xtra (colruyt.be)."""
    return await run(service().xtra_list(include_completed))


@mcp.tool(annotations=WRITE)
async def add_to_xtra_list(items: list[ListItem]) -> dict:
    """Ajoute des articles (produit ou texte libre) à la liste Xtra."""
    return await run(service().add_to_xtra_list([i.model_dump() for i in items]))


@mcp.tool(annotations=WRITE)
async def update_xtra_list_item(item_id: str, quantity: int | None = None, done: bool | None = None) -> dict:
    """Modifie la quantité d'un article de la liste Xtra ou le coche/décoche."""
    return await run(service().update_xtra_item(item_id, quantity, done))


@mcp.tool(annotations=DELETE)
async def remove_xtra_list_item(item_id: str) -> dict:
    """Supprime un article de la liste Xtra."""
    return await run(service().remove_xtra_item(item_id))


# ------------------------------------------------------------------ panier C&G
@mcp.tool(annotations=READ)
async def get_cart() -> dict:
    """Panier Collect&Go : lignes, promos, frais de service, point et créneau d'enlèvement."""
    return await run(service().cart())


@mcp.tool(annotations=WRITE)
async def add_to_cart(items: list[CartItem]) -> dict:
    """Ajoute des produits au panier Collect&Go (ne valide pas la commande)."""
    return await run(service().add_to_cart([i.model_dump() for i in items]))


@mcp.tool(annotations=DELETE)
async def update_cart_item(order_item_id: str, quantity: float) -> dict:
    """Change la quantité d'une ligne du panier (dans l'unité de la ligne). 0 = supprimer."""
    return await run(service().update_cart_item(order_item_id, quantity))


# ------------------------------------------------------------------ enlèvement
@mcp.tool(annotations=READ)
async def list_pickup_points(search: str | None = None, latitude: float | None = None,
                             longitude: float | None = None, radius_km: int = 25) -> list[dict]:
    """Points d'enlèvement Collect&Go : autour du point actuel, d'une position, ou filtrés par nom/ville/CP."""
    return await run(service().pickup_points(latitude, longitude, radius_km, search))


@mcp.tool(annotations=WRITE)
async def set_pickup_point(branch_id: str) -> dict:
    """Choisit le point d'enlèvement (branch_id de list_pickup_points)."""
    return await run(service().set_pickup_point(branch_id))


@mcp.tool(annotations=READ)
async def get_pickup_slots(days: int = 7) -> list[dict]:
    """Créneaux d'enlèvement des prochains jours, avec frais de service de chaque créneau."""
    return await run(service().pickup_slots(days))


@mcp.tool(annotations=WRITE)
async def reserve_pickup_slot(date: str, start: str) -> dict:
    """Réserve un créneau (date AAAAMMJJ, start HHMM, tels que renvoyés par get_pickup_slots).
    Ne valide pas la commande."""
    return await run(service().reserve_pickup_slot(date, start))


# ------------------------------------------------------------------ frais de service
@mcp.tool(annotations=READ)
async def list_service_fee_actions() -> list[dict]:
    """Actions « frais de service offerts » de la semaine : marques, seuil (EUR ou pièces), période."""
    actions = await run(service().service_fee_actions())
    return [{k: v for k, v in a.items() if k not in ("product_ids", "tech_ids", "sample_product")} for a in actions]


@mcp.tool(annotations=READ)
async def service_fee_action_details(action_id: str) -> dict:
    """Détail d'une action : paliers (50 % / 100 %), description et produits éligibles."""
    return await run(service().service_fee_action_details(action_id))


@mcp.tool(annotations=READ)
async def service_fee_progress() -> dict:
    """Progression du panier vers chaque seuil d'action frais de service."""
    return await run(service().service_fee_progress())


def main() -> None:
    mcp.run("stdio")
