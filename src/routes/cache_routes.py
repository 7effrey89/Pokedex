"""
Cache Routes - Handle cache management endpoints
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

cache_bp = Blueprint('cache', __name__, url_prefix='/api/cache')


@cache_bp.route('/config', methods=['GET'])
def get_cache_config():
    """Get current cache configuration and stats"""
    from src.services.cache_service import get_cache_service
    
    cache_service = get_cache_service()
    config = cache_service.get_config()
    stats = cache_service.get_stats()
    
    return jsonify({
        **config,
        **stats
    })


@cache_bp.route('/enable', methods=['POST'])
def set_cache_enabled():
    """Enable or disable caching"""
    from src.services.cache_service import get_cache_service
    
    try:
        data = request.get_json()
        enabled = data.get('enabled')
        
        if enabled is None:
            return jsonify({"error": "enabled field is required"}), 400
        
        cache_service = get_cache_service()
        cache_service.set_enabled(enabled)
        
        return jsonify({
            "message": f"Cache {'enabled' if enabled else 'disabled'}",
            "config": cache_service.get_config()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cache_bp.route('/expiry', methods=['POST'])
def set_cache_expiry():
    """Set cache expiry time in days"""
    from src.services.cache_service import get_cache_service
    
    try:
        data = request.get_json()
        days = data.get('days')
        
        if days is None:
            return jsonify({"error": "days field is required"}), 400
        
        cache_service = get_cache_service()
        cache_service.set_expiry_days(int(days))
        
        return jsonify({
            "message": f"Cache expiry set to {days} days",
            "config": cache_service.get_config()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cache_bp.route('/clear', methods=['POST'])
def clear_cache():
    """Clear all cached data"""
    from src.services.cache_service import get_cache_service
    
    try:
        cache_service = get_cache_service()
        count = cache_service.clear()
        
        return jsonify({
            "message": f"Cleared {count} cache files",
            "stats": cache_service.get_stats()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cache_bp.route('/invalidate', methods=['POST'])
def invalidate_cache():
    """Invalidate specific cache entry by tool name and parameters"""
    from src.services.cache_service import get_cache_service
    
    try:
        data = request.get_json()
        tool = data.get('tool')
        params = data.get('params', {})
        
        if not tool:
            return jsonify({"error": "tool name is required"}), 400
        
        cache_service = get_cache_service()
        
        # Delete specific cache entry
        deleted = cache_service.delete(tool, params)
        
        logger.info(f"🗑️ Cache invalidation for tool: {tool}, params: {params} - Deleted: {deleted}")
        
        return jsonify({
            "message": f"Cache invalidated for {tool}",
            "tool": tool,
            "params": params,
            "deleted": deleted,
            "stats": cache_service.get_stats()
        })
    
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        return jsonify({"error": str(e)}), 500
