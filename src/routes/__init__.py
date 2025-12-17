"""
Route Modules - Organized by Feature

This package contains Flask route blueprints organized by feature:
- chat_routes.py - Chat and messaging endpoints
- realtime_routes.py - Realtime voice API endpoints
- tool_routes.py - Tool management endpoints
- cache_routes.py - Cache management endpoints
- face_routes.py - Face recognition endpoints
"""

from .chat_routes import chat_bp
from .realtime_routes import realtime_bp
from .tool_routes import tool_bp
from .cache_routes import cache_bp
from .face_routes import face_bp
from .pokeapi_routes import pokeapi_bp

__all__ = [
    'chat_bp',
    'realtime_bp',
    'tool_bp',
    'cache_bp',
    'face_bp',
    'pokeapi_bp'
]
