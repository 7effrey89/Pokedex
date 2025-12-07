"""
Pokemon lookup tools integration
Provides functions to fetch Pokemon data from PokeAPI
"""
import requests
from typing import Dict, Optional, List
from mock_pokemon_data import MOCK_POKEMON_DATA, MOCK_SPECIES_DATA, MOCK_POKEMON_LIST

class PokemonTools:
    """Tools for looking up Pokemon information"""
    
    def __init__(self):
        self.base_url = "https://pokeapi.co/api/v2"
        self.use_mock = False  # Will be set to True if API is unavailable
    
    def get_pokemon(self, name_or_id: str) -> Optional[Dict]:
        """
        Get Pokemon data by name or ID
        
        Args:
            name_or_id: Pokemon name or ID
            
        Returns:
            Dict containing Pokemon data or None if not found
        """
        # Try mock data first if enabled or use it as fallback
        if self.use_mock or name_or_id.lower() in MOCK_POKEMON_DATA:
            mock_data = MOCK_POKEMON_DATA.get(name_or_id.lower())
            if mock_data:
                print(f"Using mock data for {name_or_id}")
                return mock_data
        
        try:
            url = f"{self.base_url}/pokemon/{name_or_id.lower()}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Pokemon from API: {e}, using mock data")
            self.use_mock = True
            return MOCK_POKEMON_DATA.get(name_or_id.lower())
    
    def get_pokemon_species(self, name_or_id: str) -> Optional[Dict]:
        """
        Get Pokemon species data (includes descriptions)
        
        Args:
            name_or_id: Pokemon name or ID
            
        Returns:
            Dict containing species data or None if not found
        """
        # Try mock data first if enabled or use it as fallback
        if self.use_mock or name_or_id.lower() in MOCK_SPECIES_DATA:
            mock_data = MOCK_SPECIES_DATA.get(name_or_id.lower())
            if mock_data:
                return mock_data
        
        try:
            url = f"{self.base_url}/pokemon-species/{name_or_id.lower()}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Pokemon species from API: {e}, using mock data")
            self.use_mock = True
            return MOCK_SPECIES_DATA.get(name_or_id.lower())
    
    def format_pokemon_info(self, pokemon_data: Dict, species_data: Optional[Dict] = None) -> Dict:
        """
        Format Pokemon data for display
        
        Args:
            pokemon_data: Pokemon data from API
            species_data: Optional species data for descriptions
            
        Returns:
            Formatted Pokemon information
        """
        if not pokemon_data:
            return {}
        
        # Extract basic info
        info = {
            "name": pokemon_data.get("name", "Unknown").title(),
            "id": pokemon_data.get("id"),
            "types": [t["type"]["name"] for t in pokemon_data.get("types", [])],
            "height": pokemon_data.get("height", 0) / 10,  # Convert to meters
            "weight": pokemon_data.get("weight", 0) / 10,  # Convert to kg
            "abilities": [a["ability"]["name"] for a in pokemon_data.get("abilities", [])],
            "image": pokemon_data.get("sprites", {}).get("other", {}).get("official-artwork", {}).get("front_default") or 
                     pokemon_data.get("sprites", {}).get("front_default"),
            "sprite": pokemon_data.get("sprites", {}).get("front_default"),
        }
        
        # Add stats
        stats = {}
        for stat in pokemon_data.get("stats", []):
            stat_name = stat["stat"]["name"]
            stats[stat_name] = stat["base_stat"]
        info["stats"] = stats
        
        # Add description if species data available
        if species_data:
            # Get English description
            flavor_texts = species_data.get("flavor_text_entries", [])
            for entry in flavor_texts:
                if entry.get("language", {}).get("name") == "en":
                    info["description"] = entry.get("flavor_text", "").replace("\n", " ").replace("\f", " ")
                    break
        
        return info
    
    def search_pokemon(self, query: str) -> str:
        """
        Search for a Pokemon and return formatted information
        
        Args:
            query: Pokemon name or ID to search for
            
        Returns:
            Formatted string with Pokemon information
        """
        pokemon_data = self.get_pokemon(query)
        if not pokemon_data:
            return f"Sorry, I couldn't find information about '{query}'. Please check the spelling or try a different Pokemon."
        
        species_data = self.get_pokemon_species(query)
        info = self.format_pokemon_info(pokemon_data, species_data)
        
        # Create a formatted response
        response = f"**{info['name']}** (#{info['id']})\n\n"
        
        if info.get('description'):
            response += f"{info['description']}\n\n"
        
        response += f"**Type(s):** {', '.join(info['types']).title()}\n"
        response += f"**Height:** {info['height']}m\n"
        response += f"**Weight:** {info['weight']}kg\n"
        response += f"**Abilities:** {', '.join(info['abilities']).title()}\n\n"
        
        response += "**Base Stats:**\n"
        for stat_name, value in info['stats'].items():
            response += f"- {stat_name.replace('-', ' ').title()}: {value}\n"
        
        return response
    
    def get_pokemon_list(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        Get a list of Pokemon
        
        Args:
            limit: Number of Pokemon to fetch
            offset: Starting offset
            
        Returns:
            List of Pokemon names
        """
        if self.use_mock:
            return MOCK_POKEMON_LIST[:limit]
        
        try:
            url = f"{self.base_url}/pokemon?limit={limit}&offset={offset}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except requests.RequestException as e:
            print(f"Error fetching Pokemon list from API: {e}, using mock data")
            self.use_mock = True
            return MOCK_POKEMON_LIST[:limit]
