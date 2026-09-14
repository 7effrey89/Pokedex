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
from src.db.tcg_repository import SqliteTcgRepository
from src.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)

# Instantiate API client
default_tcg_api_client = pokemon_tcg_api.PokemonTCGTools()
cache_service = get_cache_service()
sqlite_tcg_repository = SqliteTcgRepository()

# Get page size from environment or use default
TCG_PAGE_SIZE = int(os.getenv('TCG_PAGE_SIZE', '250'))


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
    return sqlite_tcg_repository.search_cards(
        pokemon_name=pokemon_name,
        card_type=card_type,
        hp_min=hp_min,
        hp_max=hp_max,
        rarity=rarity,
    )


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
        cached_response = cache_service.get("get_card_price", cache_key_params)
        if cached_response:
            logger.info(f"🎯 Returning cached TCG card price for: {card_id}")
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
    return sqlite_tcg_repository.get_cards_by_set(set_id, slim=slim, limit=limit)


def handle_get_card_details(card_id: str) -> Dict[str, Any]:
    """
    Get full card details for a Pokemon TCG card by ID (for URL-based routing).
    
    Args:
        card_id: Card ID in format 'set-number' (e.g., 'sv3-25')
        
    Returns:
        Dict containing formatted card data suitable for the detail view
    """
    return sqlite_tcg_repository.get_card(card_id)


def handle_get_tcg_sets(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get all TCG sets/expansions metadata.
    
    Returns:
        Dictionary with list of sets sorted by release date (newest first)
    """
    return sqlite_tcg_repository.get_sets()
