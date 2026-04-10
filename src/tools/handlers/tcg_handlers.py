"""
Pokemon TCG API Handlers

Handles all Pokemon Trading Card Game operations:
- Search for cards by name, type, HP, rarity
- Get card pricing information
"""

from typing import Dict, Any, Optional
import logging
import os

from flask import g

from src.api import pokemon_tcg_api
from src.tools.tool_manager import tool_manager
from src.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)

# Instantiate API client
default_tcg_api_client = pokemon_tcg_api.PokemonTCGTools()
cache_service = get_cache_service()

# Get page size from environment or use default
TCG_PAGE_SIZE = int(os.getenv('TCG_PAGE_SIZE', '250'))


def _build_search_label(pokemon_name: Optional[str], card_type: Optional[str], rarity: Optional[str]) -> str:
    candidates = [pokemon_name, card_type, rarity, "filtered cards"]
    for value in candidates:
        if value:
            return str(value)
    return "filtered cards"


def _normalize_cached_search_response(
    cached: Optional[Dict[str, Any]],
    pokemon_name: Optional[str],
    card_type: Optional[str],
    hp_min: Optional[int],
    hp_max: Optional[int],
    rarity: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Ensure cached responses match the formatted shape the UI expects."""
    if not cached or not isinstance(cached, dict):
        return cached
    if "cards" in cached:
        return cached
    if "data" in cached:
        formatted_cards = default_tcg_api_client.format_cards_response(cached)
        total_count = (
            cached.get("totalCount")
            or cached.get("count")
            or len(formatted_cards)
        )
        label = _build_search_label(pokemon_name, card_type, rarity)
        if hp_min is not None or hp_max is not None:
            label = f"{label} (HP filtered)"
        return {
            "cards": formatted_cards,
            "total_count": total_count,
            "search_query": label
        }
    return cached


def _get_request_tcg_api_key() -> Optional[str]:
    try:
        api_settings = getattr(g, 'api_settings', None)
    except RuntimeError:
        api_settings = None
    if not api_settings:
        return None
    tcg_config = api_settings.get('tcg')
    if not tcg_config:
        return None
    key = tcg_config.get('api_key')
    if key:
        trimmed = str(key).strip()
        return trimmed or None
    return None


def _get_tcg_client() -> pokemon_tcg_api.PokemonTCGTools:
    api_key = _get_request_tcg_api_key()
    if not api_key:
        return default_tcg_api_client
    try:
        cached_key = getattr(g, '_tcg_client_key', None)
        cached_client = getattr(g, '_tcg_client_instance', None)
        if cached_client and cached_key == api_key:
            return cached_client
        new_client = pokemon_tcg_api.PokemonTCGTools(api_key=api_key)
        g._tcg_client_key = api_key
        g._tcg_client_instance = new_client
        return new_client
    except RuntimeError:
        return pokemon_tcg_api.PokemonTCGTools(api_key=api_key)


def handle_search_pokemon_cards(
    pokemon_name: str = None,
    card_type: str = None,
    hp_min: int = None,
    hp_max: int = None,
    rarity: str = None,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Handler for search_pokemon_cards tool - searches for Pokemon TCG cards.
    
    This is the golden standard implementation used by both chat and realtime APIs.
    
    Args:
        pokemon_name: Name of the Pokemon to search for
        card_type: Card type filter (Fire, Water, etc.)
        hp_min: Minimum HP filter
        hp_max: Maximum HP filter
        rarity: Rarity filter
        force_refresh: If True, skip cache and fetch fresh data
        
    Returns:
        Dictionary with cards array and total_count, or error
    """
    # Check cache first (stale-while-revalidate)
    cache_key_params = {
        "pokemon_name": pokemon_name.lower() if pokemon_name else None,
        "card_type": card_type,
        "hp_min": hp_min,
        "hp_max": hp_max,
        "rarity": rarity
    }
    if not force_refresh:
        cached_response, cache_status = cache_service.get_with_stale("search_pokemon_cards", cache_key_params)
        if cached_response:
            normalized_cached = _normalize_cached_search_response(
                cached_response,
                pokemon_name,
                card_type,
                hp_min,
                hp_max,
                rarity
            )
            if cache_status == 'stale':
                logger.info(
                    "⏳ Returning STALE cached TCG card search for: %s",
                    pokemon_name or card_type or "filters"
                )
                if normalized_cached and isinstance(normalized_cached, dict):
                    normalized_cached['_cache_stale'] = True
                    normalized_cached['_search_params'] = {
                        k: v for k, v in cache_key_params.items() if v is not None
                    }
            else:
                logger.info(
                    "🎯 Returning cached TCG card search for: %s",
                    pokemon_name or card_type or "filters"
                )
            return normalized_cached
    
    logger.info(f"🃏 NOT IN CACHE - Fetching from API: name='{pokemon_name}', type={card_type}, hp_min={hp_min}, hp_max={hp_max}, rarity={rarity}")
    
    use_direct_tcg = tool_manager.is_tool_enabled("pokemon_tcg")
    
    if not use_direct_tcg:
        return {"error": "TCG tools are disabled"}
    
    # Use direct Pokemon TCG API
    logger.info("📡 Using direct Pokemon TCG API...")
    client = _get_tcg_client()
    try:
        if hp_min or hp_max or card_type:
            cards_data = client.search_cards_advanced(
                types=[card_type] if card_type else None,
                hp_min=hp_min,
                hp_max=hp_max,
                page_size=TCG_PAGE_SIZE
            )
        elif pokemon_name:
            cards_data = client.search_cards(pokemon_name, page_size=TCG_PAGE_SIZE)
        else:
            return {"error": "Please specify a Pokemon name or filters"}
        
        if cards_data and cards_data.get("data"):
            formatted_cards = client.format_cards_response(cards_data)
            result = {
                "cards": formatted_cards,
                "total_count": cards_data.get("totalCount", 0),
                "search_query": pokemon_name or card_type or "filtered cards"
            }
            # Cache the successful response
            cache_service.set("search_pokemon_cards", cache_key_params, result)
            return result
    except Exception as e:
        logger.warning(f"⚠️ Direct API error: {e}")
        return {"error": str(e)}
    
    return {"error": "No TCG search results found"}


def handle_get_card_price(card_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get price information for a Pokemon TCG card by ID
    
    Args:
        card_id: Card ID in format 'set-number' (e.g., 'sv3-25')
        force_refresh: If True, skip cache and fetch fresh data
        
    Returns:
        Dict containing card pricing info from TCGPlayer and Cardmarket
    """
    # Check cache first (stale-while-revalidate)
    cache_key_params = {"card_id": card_id}
    if not force_refresh:
        cached_response, cache_status = cache_service.get_with_stale("get_card_price", cache_key_params)
        if cached_response:
            if cache_status == 'stale':
                logger.info(f"⏳ Returning STALE cached card price for: {card_id}")
                if isinstance(cached_response, dict):
                    cached_response['_cache_stale'] = True
            else:
                logger.info(f"🎯 Returning cached card price for: {card_id}")
            return cached_response
    
    logger.info(f"🎴 Getting price for card: {card_id}")
    
    client = _get_tcg_client()
    try:
        price_info = client.get_card_price(card_id)
        
        if price_info:
            result = {
                "card": price_info,
                "card_id": card_id
            }
            # Cache the successful response (prices change, so shorter cache is good)
            cache_service.set("get_card_price", cache_key_params, result)
            return result
        else:
            return {"error": f"Card not found: {card_id}"}
    except Exception as e:
        logger.warning(f"⚠️ Error fetching card price: {e}")
        return {"error": str(e)}


def _slim_card(card: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the fields needed for grid display, sorting, and filtering."""
    prices = card.get("tcgplayer", {}).get("prices", {})
    slim_prices = {}
    for variant, vals in prices.items():
        if isinstance(vals, dict):
            slim_prices[variant] = {k: vals[k] for k in ("market", "mid") if k in vals}
    return {
        "id": card.get("id"),
        "name": card.get("name"),
        "number": card.get("number"),
        "supertype": card.get("supertype"),
        "subtypes": card.get("subtypes", []),
        "types": card.get("types", []),
        "rarity": card.get("rarity"),
        "nationalPokedexNumbers": card.get("nationalPokedexNumbers", []),
        "images": {"small": (card.get("images") or {}).get("small")},
        "set": {
            "id": (card.get("set") or {}).get("id"),
            "name": (card.get("set") or {}).get("name"),
            "releaseDate": (card.get("set") or {}).get("releaseDate"),
        },
        "tcgplayer": {"prices": slim_prices} if slim_prices else {},
    }


def handle_search_cards_by_set(
    set_id: str,
    force_refresh: bool = False,
    slim: bool = False,
    limit: int = 0
) -> Dict[str, Any]:
    """
    Search for all cards in a specific TCG set/expansion.
    
    Args:
        set_id: The set ID (e.g., "sv3pt5", "base1")
        force_refresh: If True, skip cache
        slim: If True, return only fields needed for grid display
        limit: If > 0, return at most this many cards (for previews)
        
    Returns:
        Dictionary with cards array and total_count
    """
    cache_key_params = {"set_id": set_id}
    if not force_refresh:
        cached_response, cache_status = cache_service.get_with_stale("search_cards_by_set", cache_key_params)
        if cached_response:
            if cache_status == 'stale':
                logger.info("⏳ Returning STALE cached set cards for: %s", set_id)
                if isinstance(cached_response, dict):
                    cached_response['_cache_stale'] = True
            else:
                logger.info("🎯 Returning cached set cards for: %s", set_id)
            if slim and isinstance(cached_response, dict) and "cards" in cached_response:
                cards = cached_response["cards"]
                if limit > 0:
                    cards = cards[:limit]
                return {
                    **cached_response,
                    "cards": [_slim_card(c) for c in cards],
                }
            if limit > 0 and isinstance(cached_response, dict) and "cards" in cached_response:
                return {
                    **cached_response,
                    "cards": cached_response["cards"][:limit],
                }
            return cached_response

    logger.info(f"🃏 Fetching cards for set: {set_id}")

    client = _get_tcg_client()
    try:
        # Paginate to get ALL cards (some sets have >250)
        all_raw = []
        page = 1
        while True:
            cards_data = client.search_cards_by_set(set_id, page=page, page_size=TCG_PAGE_SIZE)
            if not cards_data or not cards_data.get("data"):
                break
            all_raw.extend(cards_data["data"])
            total_count = cards_data.get("totalCount", 0)
            if page * TCG_PAGE_SIZE >= total_count:
                break
            page += 1

        if all_raw:
            formatted_cards = [client.format_card_info(c) for c in all_raw]
            set_name = formatted_cards[0].get("set", {}).get("name", set_id) if formatted_cards else set_id
            result = {
                "cards": formatted_cards,
                "total_count": len(formatted_cards),
                "search_query": set_name,
                "set_id": set_id
            }
            cache_service.set("search_cards_by_set", cache_key_params, result)
            if slim:
                return {
                    **result,
                    "cards": [_slim_card(c) for c in formatted_cards],
                }
            return result
    except Exception as e:
        logger.warning(f"⚠️ Error fetching set cards: {e}")
        return {"error": str(e)}

    return {"error": f"No cards found for set: {set_id}"}


def handle_get_card_details(card_id: str) -> Dict[str, Any]:
    """
    Get full card details for a Pokemon TCG card by ID (for URL-based routing).
    
    Args:
        card_id: Card ID in format 'set-number' (e.g., 'sv3-25')
        
    Returns:
        Dict containing formatted card data suitable for the detail view
    """
    cache_key_params = {"card_id": card_id}
    cached_response, cache_status = cache_service.get_with_stale("get_card_details", cache_key_params)
    if cached_response:
        if cache_status == 'stale':
            logger.info(f"⏳ Returning STALE cached card details for: {card_id}")
            if isinstance(cached_response, dict):
                cached_response['_cache_stale'] = True
        else:
            logger.info(f"🎯 Returning cached card details for: {card_id}")
        return cached_response

    logger.info(f"🎴 Fetching card details for: {card_id}")

    client = _get_tcg_client()
    try:
        card_data = client.get_card(card_id)
        if card_data and 'data' in card_data:
            formatted = client.format_card_info(card_data['data'])
            cache_service.set("get_card_details", cache_key_params, formatted)
            return formatted
        return {"error": f"Card not found: {card_id}"}
    except Exception as e:
        logger.warning(f"⚠️ Error fetching card details: {e}")
        return {"error": str(e)}


def handle_get_tcg_sets(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get all TCG sets/expansions metadata.
    
    Returns:
        Dictionary with list of sets sorted by release date (newest first)
    """
    cache_key_params = {"all_sets": True}
    if not force_refresh:
        cached_response, cache_status = cache_service.get_with_stale("get_tcg_sets", cache_key_params)
        if cached_response:
            if cache_status == 'stale':
                logger.info("⏳ Returning STALE cached TCG sets list")
                if isinstance(cached_response, dict):
                    cached_response['_cache_stale'] = True
            else:
                logger.info("🎯 Returning cached TCG sets list")
            return cached_response

    logger.info("🃏 Fetching all TCG sets from API")

    client = _get_tcg_client()
    try:
        all_sets = []
        page = 1
        while True:
            sets_data = client.get_sets(page=page, page_size=250)
            if not sets_data or 'data' not in sets_data:
                break
            for s in sets_data['data']:
                all_sets.append({
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "series": s.get("series"),
                    "releaseDate": s.get("releaseDate"),
                    "total": s.get("total", 0),
                    "images": {
                        "logo": s.get("images", {}).get("logo"),
                        "symbol": s.get("images", {}).get("symbol"),
                    }
                })
            # Check if more pages
            total_count = sets_data.get("totalCount", 0)
            if page * 250 >= total_count:
                break
            page += 1

        # Sort newest first
        all_sets.sort(key=lambda s: s.get("releaseDate", ""), reverse=True)

        result = {
            "sets": all_sets,
            "total_count": len(all_sets)
        }
        cache_service.set("get_tcg_sets", cache_key_params, result)
        return result
    except Exception as e:
        logger.warning(f"⚠️ Error fetching TCG sets: {e}")
        return {"error": str(e)}
