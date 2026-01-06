"""
Chat Routes - Handle chat and messaging endpoints
"""

import time
import logging
from flask import Blueprint, request, jsonify, Response, g
from typing import Optional
import json

from src.utils.api_settings import resolve_api_settings

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__, url_prefix='/api')

# Store conversation history (in-memory)
conversations = {}
card_contexts = {}


def generate_response(message: str, user_id: str = "default", card_context: Optional[str] = None, context_only: bool = False, api_config: Optional[dict] = None) -> dict:
    """
    Generate a response to the user message using Azure OpenAI
    
    Args:
        message: User message
        user_id: User identifier
        card_context: Optional card context for scanned images
        context_only: If True, only update context without generating response
        
    Returns:
        Dict containing response data
    """
    from azure_openai_chat import get_azure_chat
    from src.tools.tool_handlers import execute_tool
    
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

    if not api_config:
        raise ValueError('API credentials are required to generate a response.')

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
    try:
        azure_chat = get_azure_chat()

        # Create wrapper functions that call the unified handlers
        def handle_get_pokemon_info(pokemon_name: str) -> dict:
            return execute_tool('get_pokemon', {'pokemon_name': pokemon_name})

        def handle_search_pokemon_cards(
            pokemon_name: str = None,
            card_type: str = None,
            hp_min: int = None,
            hp_max: int = None,
            rarity: str = None
        ) -> dict:
            return execute_tool('search_pokemon_cards', {
                'pokemon_name': pokemon_name,
                'card_type': card_type,
                'hp_min': hp_min,
                'hp_max': hp_max,
                'rarity': rarity
            })

        def handle_get_pokemon_list(limit: int = 10, offset: int = 0) -> dict:
            return execute_tool('get_pokemon_list', {'limit': limit, 'offset': offset})

        def handle_get_random_pokemon() -> dict:
            return execute_tool('get_random_pokemon', {})

        def handle_get_random_pokemon_from_region(region: str) -> dict:
            return execute_tool('get_random_pokemon_from_region', {'region': region})

        def handle_get_random_pokemon_by_type(pokemon_type: str) -> dict:
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
        result = azure_chat.chat(message, user_id, tool_handlers, client_config=api_config)

        response_data["message"] = result["message"]
        response_data["pokemon_data"] = result.get("pokemon_data")
        response_data["tcg_data"] = result.get("tcg_data")

    except Exception as e:
        logger.error(f"Azure OpenAI error: {e}")
        response_data["message"] = f"I'm having trouble connecting to my AI brain. Error: {str(e)}"
    
    # Add response to history
    conversations[user_id].append({
        "role": "assistant",
        "content": response_data["message"],
        "pokemon_data": response_data.get("pokemon_data"),
        "tcg_data": response_data.get("tcg_data"),
        "timestamp": response_data["timestamp"]
    })
    
    return response_data


@chat_bp.route('/chat', methods=['POST'])
def chat():
    """
    Handle chat messages
    
    Expects JSON: {"message": "user message", "user_id": "optional_user_id", "card_context": "optional"}
    Returns JSON: {"message": "response", "pokemon_data": {...}, "timestamp": float}
    """
    try:
        data = request.get_json()
        message = data.get('message', '')
        user_id = data.get('user_id', 'default')
        card_context = data.get('card_context')
        api_settings_payload = data.get('api_settings')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400

        try:
            api_settings = resolve_api_settings(api_settings_payload, require_chat=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        g.api_settings = api_settings
        
        response_data = generate_response(message, user_id, card_context, api_config=api_settings['chat'])
        return jsonify(response_data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/chat/stream', methods=['POST'])
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
        api_settings_payload = data.get('api_settings')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400

        try:
            api_settings = resolve_api_settings(api_settings_payload, require_chat=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        g.api_settings = api_settings
        
        def generate():
            response_data = generate_response(message, user_id, card_context, api_config=api_settings['chat'])
            
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


@chat_bp.route('/history/<user_id>', methods=['GET'])
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


@chat_bp.route('/chat/record', methods=['POST'])
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


@chat_bp.route('/random-pokemon', methods=['GET'])
def random_pokemon_tool():
    """Return a random Pokemon result via the shared tool handlers."""
    try:
        from src.tools.tool_handlers import execute_tool
        result = execute_tool('get_random_pokemon', {})
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
