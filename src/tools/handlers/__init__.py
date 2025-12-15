"""
Tool Handlers - Organized by API Category

This package contains modular tool handlers organized by API type:
- pokemon_handlers.py - PokeAPI Pokemon data handlers
- tcg_handlers.py - Pokemon TCG API card handlers
- formatters.py - Shared formatting utilities
"""

from .pokemon_handlers import (
    handle_get_pokemon,
    handle_get_random_pokemon,
    handle_get_random_pokemon_from_region,
    handle_get_random_pokemon_by_type,
    handle_get_pokemon_list
)

from .tcg_handlers import (
    handle_search_pokemon_cards,
    handle_get_card_price
)

__all__ = [
    # Pokemon handlers
    'handle_get_pokemon',
    'handle_get_random_pokemon',
    'handle_get_random_pokemon_from_region',
    'handle_get_random_pokemon_by_type',
    'handle_get_pokemon_list',
    
    # TCG handlers
    'handle_search_pokemon_cards',
    'handle_get_card_price',
]
