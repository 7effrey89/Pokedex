"""
Pokemon TCG API Handlers

Handles all Pokemon Trading Card Game operations:
- Search for cards by name, type, HP, rarity
- Get card pricing information
"""

from typing import Dict, Any, Optional
import logging
import os

from src.api import pokemon_tcg_api
from src.tools.tool_manager import tool_manager
from src.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)

# Instantiate API client
tcg_api_client = pokemon_tcg_api.PokemonTCGTools()
cache_service = get_cache_service()

# Get page size from environment or use default
TCG_PAGE_SIZE = int(os.getenv('TCG_PAGE_SIZE', '250'))


def handle_search_pokemon_cards(
    pokemon_name: str = None,
    card_type: str = None,
    hp_min: int = None,
    hp_max: int = None,
    rarity: str = None
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
        
    Returns:
        Dictionary with cards array and total_count, or error
    """
    # Check cache first
    cache_key_params = {
        "pokemon_name": pokemon_name.lower() if pokemon_name else None,
        "card_type": card_type,
        "hp_min": hp_min,
        "hp_max": hp_max,
        "rarity": rarity
    }
    cached_response = cache_service.get("search_pokemon_cards", cache_key_params)
    if cached_response:
        logger.info(f"🎯 Returning cached TCG card search for: {pokemon_name}")
        return cached_response
    
    logger.info(f"🃏 NOT IN CACHE - Fetching from API: name='{pokemon_name}', type={card_type}, hp_min={hp_min}, hp_max={hp_max}, rarity={rarity}")
    
    use_direct_tcg = tool_manager.is_tool_enabled("pokemon_tcg")
    
    if not use_direct_tcg:
        return {"error": "TCG tools are disabled"}
    
    # Use direct Pokemon TCG API
    logger.info("📡 Using direct Pokemon TCG API...")
    try:
        if hp_min or hp_max or card_type:
            cards_data = tcg_api_client.search_cards_advanced(
                types=[card_type] if card_type else None,
                hp_min=hp_min,
                hp_max=hp_max,
                page_size=TCG_PAGE_SIZE
            )
        elif pokemon_name:
            cards_data = tcg_api_client.search_cards(pokemon_name, page_size=TCG_PAGE_SIZE)
        else:
            return {"error": "Please specify a Pokemon name or filters"}
        
        if cards_data and cards_data.get("data"):
            formatted_cards = tcg_api_client.format_cards_response(cards_data)
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


def handle_get_card_price(card_id: str) -> Dict[str, Any]:
    """
    Get price information for a Pokemon TCG card by ID
    
    Args:
        card_id: Card ID in format 'set-number' (e.g., 'sv3-25')
        
    Returns:
        Dict containing card pricing info from TCGPlayer and Cardmarket
    """
    # Check cache first
    cache_key_params = {"card_id": card_id}
    cached_response = cache_service.get("get_card_price", cache_key_params)
    if cached_response:
        logger.info(f"🎯 Returning cached card price for: {card_id}")
        return cached_response
    
    logger.info(f"🎴 Getting price for card: {card_id}")
    
    try:
        price_info = tcg_api_client.get_card_price(card_id)
        
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
