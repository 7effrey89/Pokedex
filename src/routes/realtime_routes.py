"""
Realtime Routes - Handle Azure OpenAI Realtime Voice API endpoints
"""

import logging
from flask import Blueprint, request, jsonify

from src.utils.api_settings import resolve_api_settings

logger = logging.getLogger(__name__)

realtime_bp = Blueprint('realtime', __name__, url_prefix='/api/realtime')


@realtime_bp.route('/config', methods=['POST'])
def get_realtime_connection_config():
    """
    Get WebSocket configuration for Azure OpenAI Realtime API.
    The browser will use this to establish a direct WebSocket connection.
    
    Returns:
        JSON with WebSocket URL and session configuration
    """
    from realtime_chat import get_realtime_config, get_session_config, check_realtime_availability, get_available_tools
    
    try:
        data = request.get_json() or {}
        api_settings_payload = data.get('api_settings')
        preferred_voice = data.get('voice')

        api_settings = resolve_api_settings(api_settings_payload, require_chat=True, require_realtime=True)
        realtime_config = api_settings.get('realtime')

        availability = check_realtime_availability(realtime_config)
        
        if not availability['available']:
            return jsonify({
                "error": availability['message'],
                "available": False
            }), 400
        
        config = get_realtime_config(realtime_config)
        session_config = get_session_config()
        if preferred_voice:
            session = session_config.get('session', {})
            session['voice'] = preferred_voice
        tools = get_available_tools()
        
        return jsonify({
            "available": True,
            "ws_url": config['ws_url'],
            "api_key": config['api_key'],
            "session_config": session_config,
            "tools": tools,
            "supports_image_input": True
        })
        
    except ValueError as exc:
        return jsonify({
            "error": str(exc),
            "available": False
        }), 400
    except Exception as e:
        return jsonify({
            "error": str(e),
            "available": False
        }), 500


@realtime_bp.route('/status', methods=['GET', 'POST'])
def get_realtime_status():
    """
    Check if Azure OpenAI Realtime API is available.
    
    Returns:
        JSON with availability status
    """
    from realtime_chat import check_realtime_availability
    
    data = request.get_json(silent=True) or {}
    api_settings_payload = data.get('api_settings')
    realtime_config = None
    if api_settings_payload:
        try:
            api_settings = resolve_api_settings(api_settings_payload, require_chat=True, require_realtime=True)
            realtime_config = api_settings.get('realtime')
        except ValueError as exc:
            return jsonify({"available": False, "message": str(exc)}), 400
    
    availability = check_realtime_availability(realtime_config)
    return jsonify(availability)


@realtime_bp.route('/tool', methods=['POST'])
def execute_realtime_tool():
    """
    Execute a tool call from the Realtime API.
    This endpoint allows the Realtime voice client to execute Pokemon and TCG tools.
    
    Uses the unified tool_handlers module which is shared with gpt-5-chat.
    
    Request body:
        {
            "tool_name": "get_pokemon_info",
            "arguments": {"pokemon_name": "pikachu"}
        }
    
    Returns:
        JSON with tool execution result
    """
    from src.tools.tool_handlers import execute_tool
    
    try:
        data = request.get_json()
        tool_name = data.get('tool_name')
        arguments = data.get('arguments', {})
        
        print(f"\n{'='*60}")
        print(f"🔧 REALTIME TOOL CALL")
        print(f"{'='*60}")
        print(f"📌 Tool: {tool_name}")
        print(f"📋 Arguments: {arguments}")
        
        if not tool_name:
            print(f"❌ Error: tool_name is required")
            return jsonify({"error": "tool_name is required"}), 400
        
        # Map realtime tool names to standard names if needed
        tool_name_map = {
            'get_pokemon_info': 'get_pokemon',
        }
        standard_tool_name = tool_name_map.get(tool_name, tool_name)
        
        # Use the unified tool handler
        result = execute_tool(standard_tool_name, arguments)
        
        # Log the result
        if "error" in result:
            print(f"❌ Result: ERROR - {result.get('error')}")
        else:
            result_preview = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
            print(f"✅ Result: SUCCESS")
            print(f"📦 Preview: {result_preview}")
        print(f"{'='*60}\n")
        
        return jsonify({"result": result})
        
    except Exception as e:
        print(f"💥 EXCEPTION: {str(e)}")
        print(f"{'='*60}\n")
        return jsonify({"error": str(e)}), 500
