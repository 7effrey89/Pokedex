"""
Pokemon TCG API Handlers

Handles all Pokemon Trading Card Game operations:
- Search for cards by name, type, HP, rarity
- Get card pricing information
"""

from typing import Dict, Any, Optional
import logging
import os
from datetime import datetime, timezone

from flask import g

from src.api import pokemon_tcg_api
from src.db.tcg_repository import SqliteTcgRepository
from src.services.catalog_settings import get_catalog_settings
from src.services.tcg_refresh import TcgRefreshService

logger = logging.getLogger(__name__)

# Instantiate API client
default_tcg_api_client = pokemon_tcg_api.PokemonTCGTools()
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
    if force_refresh:
        TcgRefreshService(_get_tcg_client(), sqlite_tcg_repository.database).refresh_search(
            name=pokemon_name, types=[card_type] if card_type else None,
            hp_min=hp_min, hp_max=hp_max, rarity=rarity,
        )
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
    stored = sqlite_tcg_repository.get_card_price(card_id)
    seconds = get_catalog_settings().get_config()["tcg_price_expiry_seconds"]
    refreshed_at = stored.pop("_refreshed_at", None) if stored else None
    current = seconds == 0
    if refreshed_at:
        current = current or (
            datetime.now(timezone.utc) - datetime.fromisoformat(refreshed_at)
        ).total_seconds() < seconds
    if not force_refresh and stored is not None and current:
        return {"card": stored, "card_id": card_id}
    TcgRefreshService(_get_tcg_client(), sqlite_tcg_repository.database).refresh_card(card_id)
    fresh = sqlite_tcg_repository.get_card_price(card_id)
    if fresh is None:
        raise RuntimeError(f"Refreshed TCG card {card_id} is missing from SQLite")
    fresh.pop("_refreshed_at", None)
    return {"card": fresh, "card_id": card_id}


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
    if force_refresh:
        TcgRefreshService(_get_tcg_client(), sqlite_tcg_repository.database).refresh_set(set_id)
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
    if force_refresh:
        TcgRefreshService(_get_tcg_client(), sqlite_tcg_repository.database).refresh_sets()
    return sqlite_tcg_repository.get_sets()
