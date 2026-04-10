"""
Shared Tool Handlers for Pokemon Chat Application

This module provides unified tool handling logic that is shared between
the gpt-5-chat (Azure OpenAI Chat Completions) and gpt-realtime (Azure OpenAI Realtime) APIs.

The handlers are now organized in the handlers/ subdirectory by API category:
- handlers/pokemon_handlers.py - PokeAPI Pokemon data
- handlers/tcg_handlers.py - Pokemon TCG API cards
- handlers/formatters.py - Shared formatting utilities
"""

import logging
from typing import Dict, Any

# Import modular handlers
from src.tools.handlers import (
    handle_get_pokemon,
    handle_get_random_pokemon,
    handle_get_random_pokemon_from_region,
    handle_get_random_pokemon_by_type,
    handle_get_pokemon_list,
    handle_search_pokemon_cards,
    handle_get_card_price,
    handle_get_card_details,
    handle_search_cards_by_set,
    handle_get_tcg_sets
)

logger = logging.getLogger(__name__)


# ============= Unified Tool Dispatcher =============

def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by name with the given arguments.
    
    This is the unified entry point for tool execution, used by both
    gpt-5-chat and gpt-realtime APIs.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments for the tool
        
    Returns:
        Dictionary with tool result or error
    """
    logger.info(f"🔧 Executing tool: {tool_name}")
    logger.info(f"📋 Arguments: {arguments}")
    
    try:
        if tool_name == 'get_pokemon':
            pokemon_name = arguments.get('pokemon_name', arguments.get('name', ''))
            return handle_get_pokemon(pokemon_name)
        
        elif tool_name == 'get_random_pokemon':
            return handle_get_random_pokemon()
        
        elif tool_name == 'get_random_pokemon_from_region':
            region = arguments.get('region', '')
            return handle_get_random_pokemon_from_region(region)
        
        elif tool_name == 'get_random_pokemon_by_type':
            pokemon_type = arguments.get('pokemon_type', arguments.get('type', ''))
            return handle_get_random_pokemon_by_type(pokemon_type)
        
        elif tool_name == 'get_pokemon_list':
            limit = arguments.get('limit', 10)
            offset = arguments.get('offset', 0)
            return handle_get_pokemon_list(limit, offset)
        
        elif tool_name == 'search_pokemon_cards':
            return handle_search_pokemon_cards(
                pokemon_name=arguments.get('pokemon_name', arguments.get('name', '')),
                card_type=arguments.get('card_type', arguments.get('type', None)),
                hp_min=arguments.get('hp_min', None),
                hp_max=arguments.get('hp_max', None),
                rarity=arguments.get('rarity', None),
                force_refresh=arguments.get('force_refresh', False)
            )
        
        elif tool_name == 'get_card_price':
            card_id = arguments.get('card_id', '')
            return handle_get_card_price(card_id, force_refresh=arguments.get('force_refresh', False))
        
        elif tool_name == 'get_card_details':
            card_id = arguments.get('card_id', '')
            return handle_get_card_details(card_id)
        
        elif tool_name == 'search_cards_by_set':
            set_id = arguments.get('set_id', '')
            return handle_search_cards_by_set(
                set_id=set_id,
                force_refresh=arguments.get('force_refresh', False),
                slim=arguments.get('slim', False),
                limit=int(arguments.get('limit', 0))
            )
        
        elif tool_name == 'get_tcg_sets':
            return handle_get_tcg_sets(
                force_refresh=arguments.get('force_refresh', False)
            )
        
        else:
            logger.warning(f"❓ Unknown tool: {tool_name}")
            return {"error": f"Unknown tool: {tool_name}"}
            
    except Exception as e:
        logger.error(f"💥 Tool execution error: {e}")
        return {"error": str(e)}
