"""
Flask backend for Pokemon Chat Demo
Provides API endpoints for real-time chat with Pokemon lookup capabilities
"""
import os
import json
import logging
from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from dotenv import load_dotenv
# NOTE: Direct API tools commented out - using MCP servers via tool_handlers instead
# from src.api.pokemon_api import PokemonTools
# from src.api.pokemon_tcg_api import PokemonTCGTools
from src.tools.mcp_client import (
    search_tcg_cards as mcp_search_cards, 
    get_tcg_card_price as mcp_get_price, 
    format_cards_for_display
)
from src.tools.tool_manager import tool_manager
from azure_openai_chat import get_azure_chat
from realtime_chat import get_realtime_config, get_session_config, check_realtime_availability, get_available_tools as get_realtime_tools
import time
import re
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# NOTE: Direct API tools commented out - using MCP servers via tool_handlers instead
# Initialize Pokemon tools

# Store conversation history (in-memory only - will be lost on restart)
# TODO: For production, implement persistent storage (Redis, PostgreSQL, etc.)
conversations = {}
card_contexts = {}


def generate_response(message: str, user_id: str = "default", card_context: Optional[str] = None, context_only: bool = False) -> dict:
    """
    Generate a response to the user message using Azure OpenAI
    
    Args:
        message: User message
        user_id: User identifier
        
    Returns:
        Dict containing response data
    """
    # Initialize conversation history if needed
    if user_id not in conversations:
        conversations[user_id] = []
    # Initialize card context tracking
    if user_id not in card_contexts:
        card_contexts[user_id] = None

    # Add card context as a system message if provided and changed
    if card_context:
        normalized_context = card_context.strip()
        if normalized_context and card_contexts.get(user_id) != normalized_context:
            conversations[user_id].append({
                "role": "system",
                "content": f"Card context: {normalized_context}",
                "timestamp": time.time()
            })
            card_contexts[user_id] = normalized_context

    if context_only:
        return {
            "message": "",
            "pokemon_data": None,
            "tcg_data": None,
            "timestamp": time.time()
        }

    # Add user message to history
    conversations[user_id].append({
        "role": "user",
        "content": message,
        "timestamp": time.time()
    })
    
    response_data = {
        "message": "",
        "pokemon_data": None,
        "tcg_data": None,
        "timestamp": time.time()
    }
    
    # Check if Azure OpenAI is configured
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    
    if azure_endpoint and azure_key:
        # Use Azure OpenAI for natural language understanding
        try:
            azure_chat = get_azure_chat()
            
            # Import the unified tool handlers
            from src.tools.tool_handlers import execute_tool
            
            # Create wrapper functions that call the unified handlers
            # These wrappers adapt the function signatures expected by azure_chat
            def handle_get_pokemon_info(pokemon_name: str) -> dict:
                """Handler for get_pokemon_info tool - delegates to unified handler"""
                return execute_tool('get_pokemon', {'pokemon_name': pokemon_name})
            
            def handle_search_pokemon_cards(
                pokemon_name: str = None,
                card_type: str = None,
                hp_min: int = None,
                hp_max: int = None,
                rarity: str = None
            ) -> dict:
                """Handler for search_pokemon_cards tool - delegates to unified handler"""
                return execute_tool('search_pokemon_cards', {
                    'pokemon_name': pokemon_name,
                    'card_type': card_type,
                    'hp_min': hp_min,
                    'hp_max': hp_max,
                    'rarity': rarity
                })
            
            def handle_get_pokemon_list(limit: int = 10, offset: int = 0) -> dict:
                """Handler for get_pokemon_list tool - delegates to unified handler"""
                return execute_tool('get_pokemon_list', {'limit': limit, 'offset': offset})
            
            def handle_get_random_pokemon() -> dict:
                """Handler for get_random_pokemon tool - delegates to unified handler"""
                return execute_tool('get_random_pokemon', {})
            
            def handle_get_random_pokemon_from_region(region: str) -> dict:
                """Handler for get_random_pokemon_from_region tool - delegates to unified handler"""
                return execute_tool('get_random_pokemon_from_region', {'region': region})
            
            def handle_get_random_pokemon_by_type(pokemon_type: str) -> dict:
                """Handler for get_random_pokemon_by_type tool - delegates to unified handler"""
                return execute_tool('get_random_pokemon_by_type', {'pokemon_type': pokemon_type})
            
            tool_handlers = {
                "get_pokemon_info": handle_get_pokemon_info,
                "search_pokemon_cards": handle_search_pokemon_cards,
                "get_pokemon_list": handle_get_pokemon_list,
                "get_random_pokemon": handle_get_random_pokemon,
                "get_random_pokemon_from_region": handle_get_random_pokemon_from_region,
                "get_random_pokemon_by_type": handle_get_random_pokemon_by_type
            }
            
            # Call Azure OpenAI with tools
            result = azure_chat.chat(message, user_id, tool_handlers)
            
            response_data["message"] = result["message"]
            response_data["pokemon_data"] = result.get("pokemon_data")
            response_data["tcg_data"] = result.get("tcg_data")
            
        except Exception as e:
            logger.error(f"Azure OpenAI error: {e}")
            response_data["message"] = f"I'm having trouble connecting to my AI brain. Error: {str(e)}"
    else:
        # OpenAI/Azure connection is required
        error_msg = "OpenAI connection is required. Please configure AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables."
        logger.error(error_msg)
        response_data["message"] = error_msg
    
    # Add response to history
    conversations[user_id].append({
        "role": "assistant",
        "content": response_data["message"],
        "pokemon_data": response_data.get("pokemon_data"),
        "tcg_data": response_data.get("tcg_data"),
        "timestamp": response_data["timestamp"]
    })
    
    return response_data


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handle chat messages
    
    Expects JSON: {"message": "user message", "user_id": "optional_user_id"}
    Returns JSON: {"message": "response", "pokemon_data": {...}, "timestamp": float}
    """
    try:
        data = request.get_json()
        message = data.get('message', '')
        user_id = data.get('user_id', 'default')
        card_context = data.get('card_context')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        response_data = generate_response(message, user_id, card_context)
        return jsonify(response_data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """
    Handle streaming chat responses (Server-Sent Events)
    
    Expects JSON: {"message": "user message", "user_id": "optional_user_id"}
    Returns: Server-Sent Events stream
    """
    try:
        data = request.get_json()
        message = data.get('message', '')
        user_id = data.get('user_id', 'default')
        card_context = data.get('card_context')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        def generate():
            response_data = generate_response(message, user_id, card_context)
            
            # Stream the response word by word for a typing effect
            words = response_data["message"].split()
            for i, word in enumerate(words):
                chunk = {
                    "word": word,
                    "done": i == len(words) - 1,
                    "pokemon_data": response_data["pokemon_data"] if i == len(words) - 1 else None
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                time.sleep(0.05)  # Simulate typing delay
        
        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/api/history/<user_id>', methods=['GET'])
def get_history(user_id):
    """
    Get conversation history for a user
    
    Args:
        user_id: User identifier
        
    Returns:
        JSON with conversation history
    """
    history = conversations.get(user_id, [])
    return jsonify({"history": history})


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "Pokemon Chat Demo"})


# ============= Realtime Voice API Endpoints =============

@app.route('/api/realtime/config', methods=['GET'])
def get_realtime_connection_config():
    """
    Get WebSocket configuration for Azure OpenAI Realtime API.
    The browser will use this to establish a direct WebSocket connection.
    
    Returns:
        JSON with WebSocket URL and session configuration
    """
    try:
        availability = check_realtime_availability()
        
        if not availability['available']:
            return jsonify({
                "error": availability['message'],
                "available": False
            }), 400
        
        config = get_realtime_config()
        session_config = get_session_config()
        tools = get_realtime_tools()
        
        # Check if using native MCP (tools handled by API) or function-based (client handles)
        use_native_mcp = os.getenv('USE_NATIVE_MCP', 'false').lower() == 'true'
        
        return jsonify({
            "available": True,
            "ws_url": config['ws_url'],
            "api_key": config['api_key'],
            "session_config": session_config,
            "tools": tools,
            "use_native_mcp": use_native_mcp,  # If true, API handles tool calls automatically
            "supports_image_input": True  # gpt-realtime supports image input
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "available": False
        }), 500


@app.route('/api/realtime/status', methods=['GET'])
def get_realtime_status():
    """
    Check if Azure OpenAI Realtime API is available.
    
    Returns:
        JSON with availability status
    """
    availability = check_realtime_availability()
    return jsonify(availability)


@app.route('/api/realtime/tool', methods=['POST'])
def execute_realtime_tool():
    """
    Execute a tool call from the Realtime API.
    This endpoint allows the Realtime voice client to invoke MCP servers and other tools.
    
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
            'get_pokemon_info': 'get_pokemon',  # Realtime uses get_pokemon_info
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


@app.route('/api/random-pokemon', methods=['GET'])
def random_pokemon_tool():
    """Return a random Pokemon result via the shared tool handlers."""
    try:
        from src.tools.tool_handlers import execute_tool
        result = execute_tool('get_random_pokemon', {})
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chat/record', methods=['POST'])
def record_chat_entry():
    """Store arbitrary chat entries (used by quick actions sharing tool results)."""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 'default')
        user_message = data.get('user_message')
        assistant_text = data.get('assistant_text')
        pokemon_data = data.get('pokemon_data')
        tcg_data = data.get('tcg_data')
        card_context = data.get('card_context')

        if card_context:
            generate_response('', user_id, card_context, context_only=True)

        if user_message:
            conversations.setdefault(user_id, []).append({
                "role": "user",
                "content": user_message,
                "timestamp": time.time()
            })

        if assistant_text:
            conversations.setdefault(user_id, []).append({
                "role": "assistant",
                "content": assistant_text,
                "pokemon_data": pokemon_data,
                "tcg_data": tcg_data,
                "timestamp": time.time()
            })

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============= Tool Management API Endpoints =============

@app.route('/api/tools', methods=['GET'])
def get_tools():
    """
    Get all available tools and their states
    
    Returns:
        JSON with list of all tools
    """
    return jsonify({
        "tools": tool_manager.get_all_tools(),
        "categories": tool_manager.get_categories()
    })


@app.route('/api/tools/<tool_id>', methods=['GET'])
def get_tool(tool_id):
    """
    Get a specific tool by ID
    
    Args:
        tool_id: The tool identifier
        
    Returns:
        JSON with tool data
    """
    tool = tool_manager.get_tool(tool_id)
    if not tool:
        return jsonify({"error": f"Tool '{tool_id}' not found"}), 404
    return jsonify(tool.to_dict())


@app.route('/api/tools/<tool_id>', methods=['PUT', 'PATCH'])
def update_tool(tool_id):
    """
    Update a tool's enabled state
    
    Args:
        tool_id: The tool identifier
        
    Expects JSON: {"enabled": true/false}
    Returns:
        JSON with updated tool data
    """
    try:
        data = request.get_json()
        enabled = data.get('enabled')
        
        if enabled is None:
            return jsonify({"error": "enabled field is required"}), 400
        
        success = tool_manager.set_tool_enabled(tool_id, enabled)
        if not success:
            return jsonify({"error": f"Tool '{tool_id}' not found"}), 404
        
        tool = tool_manager.get_tool(tool_id)
        return jsonify(tool.to_dict())
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tools', methods=['PUT', 'PATCH'])
def update_tools():
    """
    Update multiple tools' enabled states at once
    
    Expects JSON: {"tool_states": {"tool_id": true/false, ...}}
    Returns:
        JSON with results
    """
    try:
        data = request.get_json()
        tool_states = data.get('tool_states', {})
        
        if not tool_states:
            return jsonify({"error": "tool_states field is required"}), 400
        
        results = tool_manager.set_tools_enabled(tool_states)
        return jsonify({
            "results": results,
            "tools": tool_manager.get_all_tools()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tools/reset', methods=['POST'])
def reset_tools():
    """Reset all tools to their default states"""
    tool_manager.reset_to_defaults()
    return jsonify({
        "message": "Tools reset to defaults",
        "tools": tool_manager.get_all_tools()
    })

# ============= Face Identification API Endpoints =============

@app.route('/api/face/identify', methods=['POST'])
def identify_face():
    """
    Identify a user from a captured image using face recognition.
    
    Expects JSON: {"image": "base64_encoded_image"}
    Returns JSON: {
        "name": "person_name" or None,
        "confidence": float,
        "is_new_user": bool,
        "greeting_message": str or None,
        "error": str (optional)
    }
    """
    try:
        # Check if face identification tool is enabled
        if not tool_manager.is_tool_enabled("face_identification"):
            return jsonify({
                "error": "Face identification is disabled. Enable it in the tools settings."
            }), 403

        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({"error": "Image data is required"}), 400

        base64_image = data['image']

        # Import face recognition service
        from src.services.face_recognition_service import get_face_recognition_service

        face_service = get_face_recognition_service()
        result = face_service.identify_face_from_base64(base64_image)

        if result is None:
            return jsonify({"error": "Failed to process image"}), 500

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in face identification: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/face/status', methods=['GET'])
def get_face_recognition_status():
    """
    Get the status of the face recognition service.
    
    Returns JSON with loaded profiles and current configuration.
    """
    try:
        if not tool_manager.is_tool_enabled("face_identification"):
            return jsonify({
                "enabled": False,
                "message": "Face identification is disabled"
            })

        from src.services.face_recognition_service import get_face_recognition_service

        face_service = get_face_recognition_service()
        status = face_service.get_status()
        status['enabled'] = True

        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting face recognition status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/face/reload', methods=['POST'])
def reload_face_profiles():
    """
    Reload face profiles from the profiles_pic directory.
    Useful when new profile pictures are added.
    
    Returns JSON with reload status.
    """
    try:
        if not tool_manager.is_tool_enabled("face_identification"):
            return jsonify({
                "error": "Face identification is disabled"
            }), 403

        from src.services.face_recognition_service import get_face_recognition_service

        face_service = get_face_recognition_service()
        face_service.reload_profiles()
        status = face_service.get_status()

        return jsonify({
            "message": "Profiles reloaded successfully",
            "status": status
        })

    except Exception as e:
        logger.error(f"Error reloading face profiles: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/face/reset', methods=['POST'])
def reset_current_user():
    """
    Reset the currently identified user.
    Next identification will trigger a greeting.
    
    Returns JSON with reset status.
    """
    try:
        if not tool_manager.is_tool_enabled("face_identification"):
            return jsonify({
                "error": "Face identification is disabled"
            }), 403

        from src.services.face_recognition_service import get_face_recognition_service

        face_service = get_face_recognition_service()
        face_service.reset_current_user()

        return jsonify({
            "message": "Current user reset successfully"
        })

    except Exception as e:
        logger.error(f"Error resetting current user: {e}")
        return jsonify({"error": str(e)}), 500
# ============= TCG API Endpoints =============


if __name__ == '__main__':
    # Create templates and static directories if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('profiles_pic', exist_ok=True)
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
