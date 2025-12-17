"""
Cache Service for API responses
Stores API responses with expiration times to improve performance
"""
import json
import time
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class CacheService:
    """Manages caching of API responses with expiration"""
    
    def __init__(self, cache_dir: str = "cache"):
        """
        Initialize cache service
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.project_root = Path(__file__).resolve().parents[2]
        self._pokedex_index, self._dex_to_name = self._load_pokedex_index()
        
        # Config file for cache settings
        self.config_file = self.cache_dir / "cache_config.json"
        self.config = self._load_config()
        self._pokeapi_cache_keys = {
            "get_pokemon",
            "pokeapi_pokemon",
            "pokeapi_species",
            "pokeapi_type",
            "pokeapi_evolution_chain",
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """Load cache configuration"""
        default_config = {
            "enabled": True,
            "expiry_days": 7,
            "pokeapi_cache_enabled": True,
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Ensure all required keys exist
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.error(f"Error loading cache config: {e}")
                return default_config
        
        return default_config
    
    def _save_config(self):
        """Save cache configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache config: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current cache configuration"""
        return self.config.copy()
    
    def set_enabled(self, enabled: bool):
        """Enable or disable caching"""
        self.config["enabled"] = enabled
        self._save_config()
        logger.info(f"Cache {'enabled' if enabled else 'disabled'}")
    
    def set_expiry_days(self, days: int):
        """Set cache expiry time in days (0 = unlimited)"""
        if days < 0:
            days = 0
        if days > 90:
            days = 90
        self.config["expiry_days"] = days
        self._save_config()
        if days == 0:
            logger.info("Cache expiry set to unlimited")
        else:
            logger.info(f"Cache expiry set to {days} days")

    def set_pokeapi_cache_enabled(self, enabled: bool):
        """Enable or disable caching specifically for PokeAPI proxy calls"""
        self.config["pokeapi_cache_enabled"] = enabled
        self._save_config()
        logger.info("PokeAPI cache %s", "enabled" if enabled else "disabled")

    def should_use_pokeapi_cache(self) -> bool:
        """Check if the cache should be used for PokeAPI requests"""
        return bool(self.config.get("enabled", True) and self.config.get("pokeapi_cache_enabled", True))

    def _is_endpoint_cacheable(self, endpoint: Optional[str]) -> bool:
        """Determine whether the given endpoint should read/write cache."""
        if not self.config.get("enabled", True):
            return False
        if endpoint in self._pokeapi_cache_keys and not self.config.get("pokeapi_cache_enabled", True):
            return False
        return True
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Generate a cache key from endpoint and parameters
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Cache key (hash)
        """
        # Remove None values to normalize cache keys
        normalized_params = {k: v for k, v in params.items() if v is not None}
        
        # Create a stable string representation
        key_data = f"{endpoint}:{json.dumps(normalized_params, sort_keys=True)}"
        # Hash it for a clean filename
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cache_path(self, endpoint: str, params: Dict[str, Any], cache_key: str) -> Path:
        """Resolve the descriptive cache filename for this entry"""
        descriptor = self._build_descriptor(endpoint, params)
        if descriptor:
            safe_name = descriptor[:120]
            return self.cache_dir / f"{safe_name}.json"
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Get cached response if available and not expired
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Cached response or None if not available/expired
        """
        if not self._is_endpoint_cacheable(endpoint):
            return None
        
        if params is None:
            params = {}
        
        cache_key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(endpoint, params, cache_key)
        candidate_paths = [cache_path]
        legacy_path = self.cache_dir / f"{cache_key}.json"
        if legacy_path != cache_path:
            candidate_paths.append(legacy_path)
        
        target_path = next((p for p in candidate_paths if p.exists()), None)
        if not target_path:
            return None
        
        try:
            with target_path.open('r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check if expired
            cached_time = cached_data.get("cached_at", 0)
            expiry_days = self.config.get("expiry_days", 7)
            expiry_seconds = None if expiry_days <= 0 else expiry_days * 24 * 60 * 60

            if expiry_seconds is not None and time.time() - cached_time > expiry_seconds:
                logger.info(f"Cache expired for {endpoint}")
                target_path.unlink()
                return None
            
            logger.info(f"Cache hit for {endpoint}")
            return cached_data.get("response")
        
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
            return None
    
    def set(self, endpoint: str, params: Dict[str, Any], response: Dict[str, Any]):
        """
        Store response in cache
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            response: API response to cache
        """
        if not self._is_endpoint_cacheable(endpoint):
            return
        
        if params is None:
            params = {}
        
        cache_key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(endpoint, params, cache_key)
        
        try:
            cached_data = {
                "endpoint": endpoint,
                "params": params,
                "cache_key": cache_key,
                "response": response,
                "cached_at": time.time()
            }
            
            with cache_path.open('w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, ensure_ascii=False)

            legacy_path = self.cache_dir / f"{cache_key}.json"
            if legacy_path.exists() and legacy_path != cache_path:
                try:
                    legacy_path.unlink()
                except Exception:
                    logger.debug("Unable to remove legacy cache file for %s", endpoint)
            
            logger.info(f"Cached response for {endpoint}")
        
        except Exception as e:
            logger.error(f"Error writing cache: {e}")
    
    def clear(self) -> int:
        """
        Clear all cached data
        
        Returns:
            Number of files deleted
        """
        count = 0
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name != "cache_config.json":
                    cache_file.unlink()
                    count += 1
            logger.info(f"Cleared {count} cache files")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
        
        return count
    
    def delete(self, endpoint: str, params: Dict[str, Any] = None) -> bool:
        """
        Delete a specific cache entry
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            True if cache entry was deleted, False otherwise
        """
        if params is None:
            params = {}
        
        cache_key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(endpoint, params, cache_key)
        legacy_path = self.cache_dir / f"{cache_key}.json"
        for path in (cache_path, legacy_path):
            if path.exists():
                try:
                    path.unlink()
                    logger.info(f"Deleted cache for {endpoint} with params {params}")
                    return True
                except Exception as e:
                    logger.error(f"Error deleting cache: {e}")
                    return False
        
        logger.info(f"No cache found for {endpoint} with params {params}")
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        cache_files = [f for f in self.cache_dir.glob("*.json") if f.name != "cache_config.json"]
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            "enabled": self.config["enabled"],
            "expiry_days": self.config["expiry_days"],
            "total_files": len(cache_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }

    def _load_pokedex_index(self) -> Tuple[Dict[str, int], Dict[int, str]]:
        """Load Pokemon name to dex number mapping for descriptive filenames"""
        data_file = self.project_root / "data" / "pokemon_list.json"
        if not data_file.exists():
            return {}, {}
        try:
            with data_file.open('r', encoding='utf-8') as handle:
                entries = json.load(handle)
        except Exception:
            return {}, {}
        slug_to_number: Dict[str, int] = {}
        number_to_slug: Dict[int, str] = {}
        for entry in entries:
            raw_name = str(entry.get("name", "")).strip()
            number = entry.get("number")
            slug = self._slugify(raw_name)
            if slug and isinstance(number, int):
                slug_to_number[slug] = number
                number_to_slug[number] = slug
        return slug_to_number, number_to_slug

    def _slugify(self, value: str) -> str:
        if not value:
            return ""
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
        slug = re.sub(r"-+", "-", slug).strip('-')
        return slug

    def _resolve_pokemon_identity(self, params: Dict[str, Any], keys: Optional[Tuple[str, ...]] = None) -> Tuple[Optional[int], Optional[str]]:
        if not params:
            return None, None
        search_keys = keys or ("pokemon", "pokemon_name", "name", "species")
        for key in search_keys:
            value = params.get(key)
            if value is None:
                continue
            number, slug = self._normalize_pokemon_value(value)
            if slug:
                return number, slug
        return None, None

    def _normalize_pokemon_value(self, value: Any) -> Tuple[Optional[int], Optional[str]]:
        text = str(value).strip()
        if not text:
            return None, None
        if text.isdigit():
            number = int(text)
            slug = self._dex_to_name.get(number)
            if not slug:
                slug = self._slugify(text)
            return number, slug
        slug = self._slugify(text)
        if not slug:
            return None, None
        number = self._pokedex_index.get(slug)
        return number, slug

    def _build_descriptor(self, endpoint: str, params: Dict[str, Any]) -> Optional[str]:
        builder_map = {
            "get_pokemon": self._describe_pokemon_lookup,
            "pokeapi_pokemon": self._describe_pokemon_lookup,
            "pokeapi_species": self._describe_pokeapi_species,
            "pokeapi_type": self._describe_pokeapi_type,
            "pokeapi_evolution_chain": self._describe_pokeapi_chain,
            "search_pokemon_cards": self._describe_tcg_search,
            "get_card_price": self._describe_card_price,
        }
        builder = builder_map.get(endpoint)
        descriptor = builder(params) if builder else None
        if descriptor:
            return descriptor
        fallback = self._describe_generic(endpoint, params)
        return fallback

    def _describe_pokemon_lookup(self, params: Dict[str, Any]) -> Optional[str]:
        return self._describe_pokemon_entry(params, "pokeapi")

    def _describe_pokeapi_species(self, params: Dict[str, Any]) -> Optional[str]:
        return self._describe_pokemon_entry(params, "pokeapi-species")

    def _describe_pokeapi_type(self, params: Dict[str, Any]) -> Optional[str]:
        slug = self._slugify(str(params.get("type", "")))
        if not slug:
            return None
        return f"pokeapi-type-{slug}"

    def _describe_pokeapi_chain(self, params: Dict[str, Any]) -> Optional[str]:
        chain_id = params.get("chain")
        slug = self._slugify(str(chain_id)) if chain_id is not None else ""
        if not slug:
            return None
        return f"pokeapi-chain-{slug}"

    def _describe_pokemon_entry(self, params: Dict[str, Any], prefix: str) -> Optional[str]:
        number, slug = self._resolve_pokemon_identity(params)
        if not slug:
            return None
        if isinstance(number, int):
            return f"{prefix}-{number:04d}-{slug}"
        return f"{prefix}-{slug}"

    def _describe_tcg_search(self, params: Dict[str, Any]) -> Optional[str]:
        name = params.get("pokemon_name")
        filters = []
        if name:
            slug = self._slugify(str(name))
            number = self._pokedex_index.get(slug)
            head = f"tcg-{number:03d}-{slug}" if isinstance(number, int) else f"tcg-{slug}"
        else:
            fallback = params.get("card_type") or params.get("rarity") or "cards"
            head = f"tcg-{self._slugify(str(fallback)) or 'cards'}"
        for key in ("card_type", "rarity"):
            value = params.get(key)
            if value:
                filters.append(self._slugify(str(value)))
        if params.get("hp_min") is not None:
            filters.append(f"hpmin-{params['hp_min']}")
        if params.get("hp_max") is not None:
            filters.append(f"hpmax-{params['hp_max']}")
        suffix = "-".join(filter(None, filters))
        return f"{head}-{suffix}" if suffix else head

    def _describe_card_price(self, params: Dict[str, Any]) -> Optional[str]:
        card_id = params.get("card_id")
        if not card_id:
            return "tcg-price"
        return f"tcg-price-{self._slugify(str(card_id))}"

    def _describe_generic(self, endpoint: str, params: Dict[str, Any]) -> Optional[str]:
        base = self._slugify(endpoint) or "cache"
        if not params:
            return base
        parts = []
        for key in sorted(params.keys()):
            value = params[key]
            if value is None:
                continue
            key_slug = self._slugify(str(key))
            value_slug = self._slugify(str(value))
            if key_slug and value_slug:
                parts.append(f"{key_slug}-{value_slug}")
        if parts:
            return f"{base}-{'-'.join(parts)}"
        return base


# Global cache service instance
_cache_service = None


def get_cache_service() -> CacheService:
    """Get or create the global cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
