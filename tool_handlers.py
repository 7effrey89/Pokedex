"""
Shared Tool Handlers for Pokemon Chat Application

This module provides unified tool handling logic that is shared between
the gpt-5-chat (Azure OpenAI Chat Completions) and gpt-realtime (Azure OpenAI Realtime) APIs.

The gpt-5-chat implementation is the golden standard - changes should be made here
and will automatically apply to both APIs.
"""

import random
import requests
from typing import Dict, Any, Optional, List
import logging
import re

# Import shared modules
import pokemon_tools
import pokemon_tcg_tools
<<<<<<< HEAD
from mcp_client import (
    search_tcg_cards as mcp_search_cards,
    format_cards_for_display,
    get_pokemon_via_mcp,
    get_random_pokemon_via_mcp,
    get_random_pokemon_from_region_via_mcp,
    get_random_pokemon_by_type_via_mcp
)
=======
# NOTE: MCP client commented out - using direct APIs instead
# from mcp_client import (
#     search_tcg_cards as mcp_search_cards,
#     format_cards_for_display,
#     get_pokemon_via_mcp,
#     get_random_pokemon_via_mcp,
#     get_random_pokemon_from_region_via_mcp,
#     get_random_pokemon_by_type_via_mcp
# )
>>>>>>> origin/copilot/add-mobile-chat-demo
from tool_manager import tool_manager

logger = logging.getLogger(__name__)

<<<<<<< HEAD
=======
# Instantiate tool classes
pokemon_api = pokemon_tools.PokemonTools()
tcg_api = pokemon_tcg_tools.PokemonTCGTools()

>>>>>>> origin/copilot/add-mobile-chat-demo

def build_pokemon_assistant_text(pokemon_info: Dict[str, Any]) -> Optional[str]:
    """Generate the markdown-style assistant message for a Pokemon entry."""
    if not pokemon_info or 'name' not in pokemon_info:
        return None

    lines = []
    header = f"**{pokemon_info.get('name').title()}**"
    if pokemon_info.get('id'):
        header += f" (#{pokemon_info.get('id')})"
    lines.append(header)

    description = pokemon_info.get('description') or pokemon_info.get('mcp_text')
    if description:
        lines.append('')
        lines.append(description.strip())

    types = pokemon_info.get('types') or []
    if types:
        rendered_types = ', '.join([t.title() for t in types])
        lines.append('')
        lines.append(f"**Type(s):** {rendered_types}")

    if pokemon_info.get('height') is not None:
        lines.append(f"**Height:** {pokemon_info.get('height')}m")
    if pokemon_info.get('weight') is not None:
        lines.append(f"**Weight:** {pokemon_info.get('weight')}kg")

    abilities = pokemon_info.get('abilities') or []
    if abilities:
        rendered_abilities = ', '.join([a.title() for a in abilities])
        lines.append(f"**Abilities:** {rendered_abilities}")

    stats = pokemon_info.get('stats') or {}
    if stats:
        lines.append('')
        lines.append("**Base Stats:**")
        for stat_name, value in stats.items():
            pretty_name = stat_name.replace('-', ' ').title()
            lines.append(f"- {pretty_name}: {value}")

    markdown = '\n'.join(line for line in lines if line is not None)
    return markdown.strip() if markdown.strip() else None


def parse_mcp_markdown(text: str) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    if not text:
        return parsed

    header_match = re.search(r"#\s*(.+?)\s*\(#(\d+)\)", text)
    if header_match:
        parsed['name'] = header_match.group(1).strip()
        parsed['id'] = int(header_match.group(2))

    description_match = re.search(r"\*\*Description:\*\*\s*(.+)", text)
    if description_match:
        parsed['description'] = description_match.group(1).strip()

    types_match = re.search(r"\*\*Types:\*\*\s*(.+)", text)
    if types_match:
        types = [t.strip().title() for t in types_match.group(1).split(',') if t.strip()]
        if types:
            parsed['types'] = types

    height_match = re.search(r"\*\*Height:\*\*\s*([\d\.]+)m", text)
    if height_match:
        parsed['height'] = float(height_match.group(1))

    weight_match = re.search(r"\*\*Weight:\*\*\s*([\d\.]+)kg", text)
    if weight_match:
        parsed['weight'] = float(weight_match.group(1))

    abilities_match = re.search(r"\*\*Abilities:\*\*\s*(.+)", text)
    if abilities_match:
        abilities = [a.strip().title() for a in abilities_match.group(1).split(',') if a.strip()]
        if abilities:
            parsed['abilities'] = abilities

    return parsed


def apply_mcp_markdown_data(result: Dict[str, Any]) -> None:
    if not result or 'error' in result:
        return

    content = result.get('content', [])
    for item in content:
        if item.get('type') != 'text':
            continue
        parsed = parse_mcp_markdown(item.get('text', ''))
        if not parsed:
            continue

        # Merge parsed values into top level and pokemon_data
        pokemon_data = result.setdefault('pokemon_data', {})
        for key, value in parsed.items():
            if value is None:
                continue
            if result.get(key) is None:
                result[key] = value
            if pokemon_data.get(key) is None:
                pokemon_data[key] = value

        # Save the original markdown for reference
        if 'mcp_text' not in result:
            result['mcp_text'] = item.get('text')
        break


def build_official_artwork_url(pokemon_id: Any) -> Optional[str]:
    try:
        pokemon_id = int(pokemon_id)
    except (TypeError, ValueError):
        return None

    return (
        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"
        "/other/official-artwork/" f"{pokemon_id}.png"
    )


def extract_pokemon_identity_from_content(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for item in result.get('content', []):
        if item.get('type') != 'text':
            continue
        text = item.get('text', '')
        match = re.search(r"#\s*(.+?)\s*\(#(\d+)\)", text)
        if match:
            name = match.group(1).strip()
            try:
                pokemon_id = int(match.group(2))
            except ValueError:
                continue
            return {'name': name, 'id': pokemon_id}
    return None


def apply_official_artwork(result: Dict[str, Any]) -> None:
    if not result or 'error' in result:
        return

    pokemon_data = result.get('pokemon_data') if isinstance(result.get('pokemon_data'), dict) else {}
    pokemon_id = result.get('id') or pokemon_data.get('id')
    identity = None
    if not pokemon_id:
        identity = extract_pokemon_identity_from_content(result)
        if identity:
            pokemon_id = identity.get('id')
            if identity.get('name') and not result.get('name'):
                result['name'] = identity['name']
    if identity and identity.get('name') and not pokemon_data.get('name'):
        pokemon_data['name'] = identity['name']

    if not pokemon_id:
        return

    if not result.get('id'):
        result['id'] = pokemon_id
    if not pokemon_data.get('id'):
        pokemon_data['id'] = pokemon_id

    artwork = build_official_artwork_url(pokemon_id)
    if not artwork:
        return

    if not result.get('image'):
        result['image'] = artwork
    if not result.get('sprite'):
        result['sprite'] = artwork

    if not pokemon_data:
        pokemon_data = {}
        result['pokemon_data'] = pokemon_data
    if not pokemon_data.get('image'):
        pokemon_data['image'] = artwork
    if not pokemon_data.get('sprite'):
        pokemon_data['sprite'] = artwork


def annotate_pokemon_result_with_text(result: Dict[str, Any]) -> Dict[str, Any]:
    if not result or 'error' in result:
        return result
    if not result.get('assistant_text'):
        assistant_text = build_pokemon_assistant_text(result)
        if assistant_text:
            result['assistant_text'] = assistant_text
    apply_mcp_markdown_data(result)
    apply_official_artwork(result)
    return result


# ============= Pokemon Data Handlers =============

def handle_get_pokemon(pokemon_name: str) -> Dict[str, Any]:
    """
    Handler for get_pokemon tool - retrieves information about a specific Pokemon.
    
    Args:
        pokemon_name: Name or ID of the Pokemon to look up
        
    Returns:
        Dictionary with Pokemon data or error
    """
    use_pokeapi = tool_manager.is_tool_enabled("pokeapi")
    use_poke_mcp = tool_manager.is_tool_enabled("poke_mcp")
    
    if not use_pokeapi and not use_poke_mcp:
        return {"error": "Pokemon lookup tools are disabled. Please enable PokeAPI or Poke MCP in Tools settings."}
    
    result = None
    
    # Try MCP first if enabled
    if use_poke_mcp:
        try:
            logger.info(f"📡 Using poke-mcp for get_pokemon: {pokemon_name}")
            result = get_pokemon_via_mcp(pokemon_name)
            if result and "error" not in result:
                # If MCP returned structured fields already, return as-is (but enrich them)
                if any(k in result for k in ("name", "id", "image", "sprite")):
                    return annotate_pokemon_result_with_text(result)

                # If MCP returned a textual 'content' (markdown), try to extract name/id
                if isinstance(result, dict) and "content" in result:
                    text_content = ""
                    for c in result.get("content", []):
                        if c.get("type") == "text":
                            text_content = c.get("text", "")
                            break

                    # Attempt to parse header like: "# Pikachu (#25)"
                    m = re.search(r"#\s*(.+?)\s+\(#(\d+)\)", text_content)
                    if m:
                        parsed_name = m.group(1).strip()
                        parsed_id = m.group(2)

                        # If PokeAPI is enabled, fetch structured data to provide image/id fields
                        if use_pokeapi:
                            try:
                                pokemon_info = pokemon_tools.get_pokemon(parsed_name)
                                if pokemon_info:
                                    species_info = pokemon_tools.get_pokemon_species(parsed_name)
                                    formatted = pokemon_tools.format_pokemon_info(pokemon_info, species_info)
                                    # preserve original MCP markdown for display
                                    formatted["mcp_text"] = text_content
                                    if not formatted.get("image") and parsed_id:
                                        artwork_url = build_official_artwork_url(parsed_id)
                                        if artwork_url:
                                            formatted["image"] = artwork_url
                                            formatted["sprite"] = artwork_url
                                    return formatted
                            except Exception:
                                logger.warning("Failed to fetch structured PokeAPI data for MCP response")

                        # Return minimal structured object so frontend can render image/name/id when possible
                        fallback = {"name": parsed_name.title(), "id": int(parsed_id), "mcp_text": text_content}
                        if parsed_id:
                            artwork_url = build_official_artwork_url(parsed_id)
                            if artwork_url:
                                fallback["image"] = artwork_url
                                fallback["sprite"] = artwork_url
                        fallback["content"] = [{"type": "text", "text": text_content}]
                        return annotate_pokemon_result_with_text(fallback)

                # Otherwise return the raw MCP result
                return annotate_pokemon_result_with_text(result)
            logger.warning(f"poke-mcp error: {result.get('error')}")
        except Exception as e:
            logger.warning(f"poke-mcp exception: {e}")
    
<<<<<<< HEAD
    # Fallback to direct PokeAPI
    if use_pokeapi:
        pokemon_info = pokemon_tools.get_pokemon(pokemon_name)
        if pokemon_info:
            species_info = pokemon_tools.get_pokemon_species(pokemon_name)
            formatted = pokemon_tools.format_pokemon_info(pokemon_info, species_info)
=======
    # Use direct PokeAPI as primary method
    if use_pokeapi:
        pokemon_info = pokemon_api.get_pokemon(pokemon_name)
        if pokemon_info:
            species_info = pokemon_api.get_pokemon_species(pokemon_name)
            formatted = pokemon_api.format_pokemon_info(pokemon_info, species_info)
>>>>>>> origin/copilot/add-mobile-chat-demo
            return annotate_pokemon_result_with_text(formatted)
    
    return {"error": f"Pokemon '{pokemon_name}' not found"}


def handle_get_random_pokemon() -> Dict[str, Any]:
    """
    Handler for get_random_pokemon tool - returns a random Pokemon from the entire Pokedex.
    
    Returns:
        Dictionary with random Pokemon data or error
    """
    use_pokeapi = tool_manager.is_tool_enabled("pokeapi")
    use_poke_mcp = tool_manager.is_tool_enabled("poke_mcp")
    
    if not use_pokeapi and not use_poke_mcp:
        return {"error": "Pokemon lookup tools are disabled. Please enable PokeAPI or Poke MCP in Tools settings."}
    
    # Try MCP first if enabled
    if use_poke_mcp:
        try:
            logger.info("📡 Using poke-mcp for get_random_pokemon")
            result = get_random_pokemon_via_mcp()
            if "error" not in result:
                return annotate_pokemon_result_with_text(result)
            logger.warning(f"poke-mcp error: {result.get('error')}")
        except Exception as e:
            logger.warning(f"poke-mcp exception: {e}")
    
    # Fallback to direct PokeAPI
    if use_pokeapi:
        random_id = random.randint(1, 1000)
        pokemon_data = pokemon_tools.get_pokemon(str(random_id))
        if pokemon_data:
            species_info = pokemon_tools.get_pokemon_species(str(random_id))
            formatted = pokemon_tools.format_pokemon_info(pokemon_data, species_info)
            return annotate_pokemon_result_with_text(formatted)
    
    return {"error": "Failed to get random Pokemon"}


def handle_get_random_pokemon_from_region(region: str) -> Dict[str, Any]:
    """
    Handler for get_random_pokemon_from_region tool - returns a random Pokemon from a specific region.
    
    Args:
        region: Pokemon region name (kanto, johto, hoenn, sinnoh, unova, kalos, alola, galar, paldea)
        
    Returns:
        Dictionary with random Pokemon data from the specified region or error
    """
    use_pokeapi = tool_manager.is_tool_enabled("pokeapi")
    use_poke_mcp = tool_manager.is_tool_enabled("poke_mcp")
    
    if not use_pokeapi and not use_poke_mcp:
        return {"error": "Pokemon lookup tools are disabled. Please enable PokeAPI or Poke MCP in Tools settings."}
    
    # Try MCP first if enabled
    if use_poke_mcp:
        try:
            logger.info(f"📡 Using poke-mcp for get_random_pokemon_from_region: {region}")
            result = get_random_pokemon_from_region_via_mcp(region)
            if "error" not in result:
                return result
            logger.warning(f"poke-mcp error: {result.get('error')}")
        except Exception as e:
            logger.warning(f"poke-mcp exception: {e}")
    
    # Fallback to direct PokeAPI
    if use_pokeapi:
        # Region to Pokemon ID ranges (approximate)
        region_ranges = {
            "kanto": (1, 151),
            "johto": (152, 251),
            "hoenn": (252, 386),
            "sinnoh": (387, 493),
            "unova": (494, 649),
            "kalos": (650, 721),
            "alola": (722, 809),
            "galar": (810, 905),
            "paldea": (906, 1010)
        }
        
        region_lower = region.lower()
        if region_lower not in region_ranges:
            return {"error": f"Unknown region: {region}. Valid regions: {', '.join(region_ranges.keys())}"}
        
        start_id, end_id = region_ranges[region_lower]
        random_id = random.randint(start_id, end_id)
        pokemon_data = pokemon_tools.get_pokemon(str(random_id))
        if pokemon_data:
            species_info = pokemon_tools.get_pokemon_species(str(random_id))
            result = pokemon_tools.format_pokemon_info(pokemon_data, species_info)
            result["region"] = region.title()
            return result
    
    return {"error": f"Failed to get random Pokemon from {region}"}


def handle_get_random_pokemon_by_type(pokemon_type: str) -> Dict[str, Any]:
    """
    Handler for get_random_pokemon_by_type tool - returns a random Pokemon of a specific type.
    
    Args:
        pokemon_type: Pokemon type (fire, water, grass, electric, etc.)
        
    Returns:
        Dictionary with random Pokemon data of the specified type or error
    """
    use_pokeapi = tool_manager.is_tool_enabled("pokeapi")
    use_poke_mcp = tool_manager.is_tool_enabled("poke_mcp")
    
    if not use_pokeapi and not use_poke_mcp:
        return {"error": "Pokemon lookup tools are disabled. Please enable PokeAPI or Poke MCP in Tools settings."}
    
    # Try MCP first if enabled
    if use_poke_mcp:
        try:
            logger.info(f"📡 Using poke-mcp for get_random_pokemon_by_type: {pokemon_type}")
            result = get_random_pokemon_by_type_via_mcp(pokemon_type)
            if "error" not in result:
                return result
            logger.warning(f"poke-mcp error: {result.get('error')}")
        except Exception as e:
            logger.warning(f"poke-mcp exception: {e}")
    
    # Fallback to direct PokeAPI
    if use_pokeapi:
        try:
            response = requests.get(f"https://pokeapi.co/api/v2/type/{pokemon_type.lower()}", timeout=10)
            if response.status_code == 200:
                type_data = response.json()
                pokemon_list = type_data.get("pokemon", [])
                if pokemon_list:
                    random_pokemon = random.choice(pokemon_list)
                    pokemon_name = random_pokemon["pokemon"]["name"]
                    pokemon_data = pokemon_tools.get_pokemon(pokemon_name)
                    if pokemon_data:
                        species_info = pokemon_tools.get_pokemon_species(pokemon_name)
                        return pokemon_tools.format_pokemon_info(pokemon_data, species_info)
                    return {"error": f"Failed to get {pokemon_type} Pokemon"}
                return {"error": f"No {pokemon_type} type Pokemon found"}
            return {"error": f"Invalid type: {pokemon_type}"}
        except Exception as e:
            return {"error": str(e)}
    
    return {"error": f"Failed to get {pokemon_type} Pokemon"}


def handle_get_pokemon_list(limit: int = 10, offset: int = 0) -> Dict[str, Any]:
    """
    Handler for get_pokemon_list tool - returns a list of Pokemon names.
    
    Args:
        limit: Maximum number of Pokemon to return (capped at 50)
        offset: Starting position in the list
        
    Returns:
        Dictionary with list of Pokemon names or error
    """
    if not tool_manager.is_tool_enabled("pokeapi"):
        return {"error": "PokeAPI tool is disabled"}
    
    limit = min(limit, 50)  # Cap at 50
    pokemon_list = pokemon_tools.get_pokemon_list(limit=limit, offset=offset)
    return {
        "pokemon": [p['name'].title() for p in pokemon_list],
        "count": len(pokemon_list)
    }


# ============= TCG Card Handlers =============

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
    logger.info(f"🃏 Searching for TCG cards: name='{pokemon_name}', type={card_type}, hp_min={hp_min}, hp_max={hp_max}, rarity={rarity}")
    
    use_mcp_tcg = tool_manager.is_tool_enabled("pokemon_tcg_mcp")
    use_direct_tcg = tool_manager.is_tool_enabled("pokemon_tcg")
    
    if not use_mcp_tcg and not use_direct_tcg:
        return {"error": "TCG tools are disabled"}
    
    # Try MCP first if enabled
    if use_mcp_tcg:
        try:
            logger.info("📡 Using ptcg-mcp server...")
            
            # Build HP filter string if needed
            hp_filter = None
            if hp_min and hp_max:
                hp_filter = f"[{hp_min} TO {hp_max}]"
            elif hp_min:
                hp_filter = f"[{hp_min} TO *]"
            elif hp_max:
                hp_filter = f"[* TO {hp_max}]"
            
            result = mcp_search_cards(
                name=pokemon_name,
                types=card_type,
                hp=hp_filter,
                rarity=rarity,
                page_size=6
            )
            
            logger.info(f"✅ ptcg-mcp returned: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            
            formatted = format_cards_for_display(result)
            if "cards" in formatted:
                return {
                    "cards": formatted["cards"],
                    "total_count": formatted.get("count", len(formatted["cards"])),
                    "search_query": pokemon_name or card_type or "filtered cards"
                }
            
            # If MCP returned a message (like "no cards found"), check if we should fallback
            if "message" in formatted and use_direct_tcg:
                logger.info(f"MCP message: {formatted['message']}, trying direct API...")
            else:
                return {"error": formatted.get("message", "No cards found"), "search_query": pokemon_name or ""}
                
        except Exception as e:
            logger.warning(f"⚠️ MCP error: {e}")
            if not use_direct_tcg:
                return {"error": str(e)}
    
<<<<<<< HEAD
    # Fallback to direct Pokemon TCG API
=======
    # Use direct Pokemon TCG API as primary method
>>>>>>> origin/copilot/add-mobile-chat-demo
    if use_direct_tcg:
        logger.info("📡 Using direct Pokemon TCG API...")
        try:
            if hp_min or hp_max or card_type:
<<<<<<< HEAD
                cards_data = pokemon_tcg_tools.search_cards_advanced(
=======
                cards_data = tcg_api.search_cards_advanced(
>>>>>>> origin/copilot/add-mobile-chat-demo
                    types=[card_type] if card_type else None,
                    hp_min=hp_min,
                    hp_max=hp_max,
                    page_size=6
                )
            elif pokemon_name:
<<<<<<< HEAD
                cards_data = pokemon_tcg_tools.search_cards(pokemon_name, page_size=6)
=======
                cards_data = tcg_api.search_cards(pokemon_name, page_size=6)
>>>>>>> origin/copilot/add-mobile-chat-demo
            else:
                return {"error": "Please specify a Pokemon name or filters"}
            
            if cards_data and cards_data.get("data"):
<<<<<<< HEAD
                formatted_cards = pokemon_tcg_tools.format_cards_response(cards_data)
=======
                formatted_cards = tcg_api.format_cards_response(cards_data)
>>>>>>> origin/copilot/add-mobile-chat-demo
                return {
                    "cards": formatted_cards,
                    "total_count": cards_data.get("totalCount", 0),
                    "search_query": pokemon_name or card_type or "filtered cards"
                }
        except Exception as e:
            logger.warning(f"⚠️ Direct API error: {e}")
            return {"error": str(e)}
    
<<<<<<< HEAD
    return {"error": "No cards found", "search_query": pokemon_name or ""}


=======
    return {"error": "No TCG search results found"}
    
    return {"error": "No cards found", "search_query": pokemon_name or ""}


def handle_get_card_price(card_id: str) -> Dict:
    """
    Get price information for a Pokemon TCG card by ID
    
    Args:
        card_id: Card ID in format 'set-number' (e.g., 'sv3-25')
        
    Returns:
        Dict containing card pricing info from TCGPlayer and Cardmarket
    """
    logger.info(f"🎴 Getting price for card: {card_id}")
    
    try:
        price_info = tcg_api.get_card_price(card_id)
        
        if price_info:
            return {
                "card": price_info,
                "card_id": card_id
            }
        else:
            return {"error": f"Card not found: {card_id}"}
    except Exception as e:
        logger.warning(f"⚠️ Error fetching card price: {e}")
        return {"error": str(e)}


>>>>>>> origin/copilot/add-mobile-chat-demo
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
                rarity=arguments.get('rarity', None)
            )
        
<<<<<<< HEAD
=======
        elif tool_name == 'get_card_price':
            card_id = arguments.get('card_id', '')
            return handle_get_card_price(card_id)
        
>>>>>>> origin/copilot/add-mobile-chat-demo
        else:
            logger.warning(f"❓ Unknown tool: {tool_name}")
            return {"error": f"Unknown tool: {tool_name}"}
            
    except Exception as e:
        logger.error(f"💥 Tool execution error: {e}")
        return {"error": str(e)}
