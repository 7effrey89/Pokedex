"""
Pokemon Trading Card Game lookup tools
Provides functions to fetch Pokemon TCG card data from the Pokemon TCG API
https://pokemontcg.io/
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Optional, List
import os


class PokemonTCGTools:
    """Tools for looking up Pokemon Trading Card Game information"""
    
    def __init__(self):
        self.base_url = "https://api.pokemontcg.io/v2"
        self.headers = {
            "Content-Type": "application/json"
        }
        self.timeout = 30  # Increased timeout
        
        # Optional: Add API key for higher rate limits (free at pokemontcg.io)
        api_key = os.environ.get("POKEMON_TCG_API_KEY", "")
        if api_key:
            self.headers["X-Api-Key"] = api_key
        
        # Set up session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
    
    def search_cards(self, query: str, page: int = 1, page_size: int = 10) -> Optional[Dict]:
        """
        Search for Pokemon TCG cards
        
        Args:
            query: Search query (card name, pokemon name, etc.)
            page: Page number for pagination
            page_size: Number of results per page
            
        Returns:
            Dict containing card search results or None if error
        """
        try:
            # Build the search query - search by name
            params = {
                "q": f"name:{query}*",
                "page": page,
                "pageSize": page_size,
                "orderBy": "-set.releaseDate"  # Most recent first
            }
            
            url = f"{self.base_url}/cards"
            response = self.session.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error searching TCG cards: {e}")
            return None
    
    def search_cards_advanced(self, 
                              name: str = None,
                              types: List[str] = None,
                              subtypes: List[str] = None,
                              hp_min: int = None,
                              hp_max: int = None,
                              legality: str = None,
                              retreat_cost: int = None,
                              page: int = 1,
                              page_size: int = 10) -> Optional[Dict]:
        """
        Advanced search for Pokemon TCG cards with multiple filters
        
        Args:
            name: Card name (supports wildcards with *)
            types: List of types (Water, Fire, Grass, etc.)
            subtypes: List of subtypes (Basic, EX, GX, V, VMAX, etc.)
            hp_min: Minimum HP
            hp_max: Maximum HP
            legality: Format legality (standard, expanded, unlimited)
            retreat_cost: Retreat cost (0 for free retreat)
            page: Page number
            page_size: Results per page
            
        Returns:
            Dict containing card search results
        """
        try:
            query_parts = []
            
            if name:
                # Support exact match with ! prefix
                if name.startswith("!"):
                    query_parts.append(f'name:"{name[1:]}"')
                else:
                    query_parts.append(f"name:{name}*")
            
            if types:
                for t in types:
                    query_parts.append(f"types:{t}")
            
            if subtypes:
                for st in subtypes:
                    query_parts.append(f"subtypes:{st}")
            
            if hp_min is not None and hp_max is not None:
                query_parts.append(f"hp:[{hp_min} TO {hp_max}]")
            elif hp_min is not None:
                query_parts.append(f"hp:[{hp_min} TO *]")
            elif hp_max is not None:
                query_parts.append(f"hp:[* TO {hp_max}]")
            
            if legality:
                query_parts.append(f"legalities.{legality}:legal")
            
            if retreat_cost is not None:
                query_parts.append(f"convertedRetreatCost:{retreat_cost}")
            
            query = " ".join(query_parts) if query_parts else "*"
            
            params = {
                "q": query,
                "page": page,
                "pageSize": page_size,
                "orderBy": "-set.releaseDate"
            }
            
            url = f"{self.base_url}/cards"
            response = self.session.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error in advanced TCG search: {e}")
            return None
    
    def get_card(self, card_id: str) -> Optional[Dict]:
        """
        Get a specific card by ID
        
        Args:
            card_id: The card ID (e.g., "base1-4" for Charizard)
            
        Returns:
            Dict containing card data or None if not found
        """
        try:
            url = f"{self.base_url}/cards/{card_id}"
            response = self.session.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching TCG card: {e}")
            return None
    
    def get_sets(self, page: int = 1, page_size: int = 50) -> Optional[Dict]:
        """
        Get list of TCG sets
        
        Args:
            page: Page number
            page_size: Results per page
            
        Returns:
            Dict containing set data
        """
        try:
            params = {
                "page": page,
                "pageSize": page_size,
                "orderBy": "-releaseDate"
            }
            
            url = f"{self.base_url}/sets"
            response = self.session.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching TCG sets: {e}")
            return None
    
    def format_card_info(self, card: Dict) -> Dict:
        """
        Format card data for display
        
        Args:
            card: Card data from API
            
        Returns:
            Formatted card information
        """
        if not card:
            return {}
        
        info = {
            "id": card.get("id"),
            "name": card.get("name", "Unknown"),
            "supertype": card.get("supertype"),  # Pokémon, Trainer, Energy
            "subtypes": card.get("subtypes", []),
            "types": card.get("types", []),
            "hp": card.get("hp"),
            "evolvesFrom": card.get("evolvesFrom"),
            "evolvesTo": card.get("evolvesTo", []),
            "abilities": card.get("abilities", []),
            "attacks": card.get("attacks", []),
            "weaknesses": card.get("weaknesses", []),
            "resistances": card.get("resistances", []),
            "retreatCost": card.get("retreatCost", []),
            "convertedRetreatCost": card.get("convertedRetreatCost", 0),
            "set": {
                "name": card.get("set", {}).get("name"),
                "series": card.get("set", {}).get("series"),
                "releaseDate": card.get("set", {}).get("releaseDate"),
                "logo": card.get("set", {}).get("images", {}).get("logo"),
                "symbol": card.get("set", {}).get("images", {}).get("symbol")
            },
            "number": card.get("number"),
            "rarity": card.get("rarity"),
            "flavorText": card.get("flavorText"),
            "artist": card.get("artist"),
            "legalities": card.get("legalities", {}),
            "images": {
                "small": card.get("images", {}).get("small"),
                "large": card.get("images", {}).get("large")
            },
            "tcgplayer": card.get("tcgplayer", {}),
            "cardmarket": card.get("cardmarket", {})
        }
        
        return info
    
    def format_cards_response(self, cards_data: Dict) -> List[Dict]:
        """
        Format multiple cards for display
        
        Args:
            cards_data: Response from card search API
            
        Returns:
            List of formatted card information
        """
        if not cards_data or "data" not in cards_data:
            return []
        
        return [self.format_card_info(card) for card in cards_data.get("data", [])]
    
    def search_pokemon_cards(self, pokemon_name: str) -> str:
        """
        Search for TCG cards of a specific Pokemon and return formatted response
        
        Args:
            pokemon_name: Name of the Pokemon
            
        Returns:
            Formatted string with card information
        """
        cards_data = self.search_cards(pokemon_name, page_size=5)
        
        if not cards_data or not cards_data.get("data"):
            return f"Sorry, I couldn't find any trading cards for '{pokemon_name}'."
        
        cards = self.format_cards_response(cards_data)
        total = cards_data.get("totalCount", 0)
        
        response = f"**{pokemon_name.title()} Trading Cards** ({total} total cards found)\n\n"
        
        for card in cards[:5]:
            response += f"**{card['name']}**"
            if card.get('set', {}).get('name'):
                response += f" - {card['set']['name']}"
            response += "\n"
            
            if card.get('types'):
                response += f"Type: {', '.join(card['types'])} | "
            if card.get('hp'):
                response += f"HP: {card['hp']} | "
            if card.get('rarity'):
                response += f"Rarity: {card['rarity']}"
            response += "\n"
            
            if card.get('legalities'):
                legal_formats = [k.title() for k, v in card['legalities'].items() if v == 'Legal']
                if legal_formats:
                    response += f"Legal in: {', '.join(legal_formats)}\n"
            
            response += "\n"
        
        if total > 5:
            response += f"_...and {total - 5} more cards_"
        
        return response
