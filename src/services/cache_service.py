"""
Cache Service for API responses
Stores API responses with expiration times to improve performance
"""
import json
import os
import time
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path
import logging

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
        
        # Config file for cache settings
        self.config_file = self.cache_dir / "cache_config.json"
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load cache configuration"""
        default_config = {
            "enabled": True,
            "expiry_days": 7
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
        """Set cache expiry time in days"""
        if days < 1:
            days = 1
        if days > 90:
            days = 90
        self.config["expiry_days"] = days
        self._save_config()
        logger.info(f"Cache expiry set to {days} days")
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Generate a cache key from endpoint and parameters
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Cache key (hash)
        """
        # Create a stable string representation
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        # Hash it for a clean filename
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key"""
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
        if not self.config["enabled"]:
            return None
        
        if params is None:
            params = {}
        
        cache_key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
            
            # Check if expired
            cached_time = cached_data.get("cached_at", 0)
            expiry_seconds = self.config["expiry_days"] * 24 * 60 * 60
            
            if time.time() - cached_time > expiry_seconds:
                logger.info(f"Cache expired for {endpoint}")
                cache_path.unlink()  # Delete expired cache
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
        if not self.config["enabled"]:
            return
        
        if params is None:
            params = {}
        
        cache_key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            cached_data = {
                "endpoint": endpoint,
                "params": params,
                "response": response,
                "cached_at": time.time()
            }
            
            with open(cache_path, 'w') as f:
                json.dump(cached_data, f, indent=2)
            
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


# Global cache service instance
_cache_service = None


def get_cache_service() -> CacheService:
    """Get or create the global cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
