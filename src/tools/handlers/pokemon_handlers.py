"""
Pokemon API Handlers

Handles all Pokemon data lookups via PokeAPI:
- Get specific Pokemon by name/ID
- Get random Pokemon (all, by region, by type)
- Get Pokemon lists
"""

import random
import requests
from typing import Dict, Any
import logging

from src.api import pokemon_api
from src.tools.tool_manager import tool_manager
from src.services.cache_service import get_cache_service
from .formatters import annotate_pokemon_result_with_text

logger = logging.getLogger(__name__)

# Instantiate API client
pokemon_api_client = pokemon_api.PokemonTools()
cache_service = get_cache_service()


def handle_get_pokemon(pokemon_name: str) -> Dict[str, Any]:
    """
    Handler for get_pokemon tool - retrieves information about a specific Pokemon.
    
    Args:
        pokemon_name: Name or ID of the Pokemon to look up
        
    Returns:
        Dictionary with Pokemon data or error
    """
    # Check cache first
    cache_key_params = {"pokemon_name": pokemon_name.lower()}
    cached_response = cache_service.get("get_pokemon", cache_key_params)
    if cached_response:
        logger.info(f"🎯 Returning cached Pokemon data for: {pokemon_name}")
        return cached_response
    
    use_pokeapi = tool_manager.is_tool_enabled("pokeapi")
    
    if not use_pokeapi:
        return {"error": "Pokemon lookup tools are disabled. Please enable PokeAPI in Tools settings."}
    
    # Use direct PokeAPI
    pokemon_info = pokemon_api_client.get_pokemon(pokemon_name)
    if pokemon_info:
        species_info = pokemon_api_client.get_pokemon_species(pokemon_name)
        formatted = pokemon_api_client.format_pokemon_info(pokemon_info, species_info)
        result = annotate_pokemon_result_with_text(formatted)
        # Cache the successful response
        cache_service.set("get_pokemon", cache_key_params, result)
        return result
    
    return {"error": f"Pokemon '{pokemon_name}' not found"}


def handle_get_random_pokemon() -> Dict[str, Any]:
    """
    Handler for get_random_pokemon tool - returns a random Pokemon from the entire Pokedex.
    
    Returns:
        Dictionary with random Pokemon data or error
    """
    use_pokeapi = tool_manager.is_tool_enabled("pokeapi")
    
    if not use_pokeapi:
        return {"error": "Pokemon lookup tools are disabled. Please enable PokeAPI in Tools settings."}
    
    # Use direct PokeAPI
    random_id = random.randint(1, 1000)
    pokemon_data = pokemon_api_client.get_pokemon(str(random_id))
    if pokemon_data:
        species_info = pokemon_api_client.get_pokemon_species(str(random_id))
        formatted = pokemon_api_client.format_pokemon_info(pokemon_data, species_info)
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
    
    if not use_pokeapi:
        return {"error": "Pokemon lookup tools are disabled"}
    
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
    pokemon_data = pokemon_api_client.get_pokemon(str(random_id))
    if pokemon_data:
        species_info = pokemon_api_client.get_pokemon_species(str(random_id))
        result = pokemon_api_client.format_pokemon_info(pokemon_data, species_info)
        result["region"] = region.title()
        return annotate_pokemon_result_with_text(result)
    
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
    
    if not use_pokeapi:
        return {"error": "Pokemon lookup tools are disabled"}
    
    try:
        response = requests.get(f"https://pokeapi.co/api/v2/type/{pokemon_type.lower()}", timeout=10)
        if response.status_code == 200:
            type_data = response.json()
            pokemon_list = type_data.get("pokemon", [])
            if pokemon_list:
                random_pokemon = random.choice(pokemon_list)
                pokemon_name = random_pokemon["pokemon"]["name"]
                pokemon_data = pokemon_api_client.get_pokemon(pokemon_name)
                if pokemon_data:
                    species_info = pokemon_api_client.get_pokemon_species(pokemon_name)
                    formatted = pokemon_api_client.format_pokemon_info(pokemon_data, species_info)
                    return annotate_pokemon_result_with_text(formatted)
                return {"error": f"Failed to get {pokemon_type} Pokemon"}
            return {"error": f"No {pokemon_type} type Pokemon found"}
        return {"error": f"Invalid type: {pokemon_type}"}
    except Exception as e:
        return {"error": str(e)}


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
    pokemon_list = pokemon_api_client.get_pokemon_list(limit=limit, offset=offset)
    return {
        "pokemon": [p['name'].title() for p in pokemon_list],
        "count": len(pokemon_list)
    }
