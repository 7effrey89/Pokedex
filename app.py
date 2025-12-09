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
from pokemon_tools import PokemonTools
from pokemon_tcg_tools import PokemonTCGTools
from mcp_client import (
    search_tcg_cards as mcp_search_cards, 
    get_tcg_card_price as mcp_get_price, 
    format_cards_for_display
)
from tool_manager import tool_manager
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

# Initialize Pokemon tools
pokemon_tools = PokemonTools()
pokemon_tcg_tools = PokemonTCGTools()

# Store conversation history (in-memory only - will be lost on restart)
# TODO: For production, implement persistent storage (Redis, PostgreSQL, etc.)
conversations = {}
card_contexts = {}


def detect_pokemon_query(message: str) -> tuple:
    """
    Detect if the message is asking about a Pokemon
    
    Args:
        message: User message
        
    Returns:
        Tuple of (is_pokemon_query, pokemon_name)
    """
    message_lower = message.lower()
    
    # Common patterns for Pokemon queries
    patterns = [
        r"tell me about (\w+)",
        r"what is (\w+)",
        r"who is (\w+)",
        r"show me (\w+)",
        r"information about (\w+)",
        r"info on (\w+)",
        r"search for (\w+)",
        r"look up (\w+)",
        r"find (\w+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            return True, match.group(1)
    
    # Check if message contains just a Pokemon name or ID
    words = message_lower.split()
    if len(words) == 1 or (len(words) == 2 and words[0] in ['pokemon', 'show', 'find']):
        potential_name = words[-1]
        return True, potential_name
    
    return False, None


def detect_tcg_query(message: str) -> tuple:
    """
    Detect if the message is asking about Pokemon Trading Cards
    
    Args:
        message: User message
        
    Returns:
        Tuple of (is_tcg_query, search_params dict or pokemon_name string)
    """
    message_lower = message.lower()
    
    # TCG-specific keywords
    tcg_keywords = ['card', 'cards', 'tcg', 'trading card', 'deck', 'collection']
    has_tcg_keyword = any(kw in message_lower for kw in tcg_keywords)
    
    # Advanced filter keywords that suggest TCG search (HP, types with filters, etc.)
    advanced_keywords = ['hp', 'hit points', 'retreat', 'standard', 'expanded', 'legal', 'banned']
    has_advanced_keyword = any(kw in message_lower for kw in advanced_keywords)
    
    # Type keywords
    pokemon_types = ['water', 'fire', 'grass', 'electric', 'psychic', 'fighting', 
                     'dark', 'darkness', 'steel', 'metal', 'dragon', 'fairy', 'normal', 'colorless']
    
    # Check for type + filter pattern (e.g., "water-type Pokemon with more than 120 HP")
    type_filter_pattern = r'(water|fire|grass|electric|psychic|fighting|dark|steel|dragon|fairy|normal|colorless)[\s-]*type'
    type_match = re.search(type_filter_pattern, message_lower)
    
    # Check for HP filter
    hp_pattern = r'(?:more than|over|above|greater than|at least|minimum|>\s*)(\d+)\s*(?:hp|hit points)'
    hp_match = re.search(hp_pattern, message_lower)
    
    hp_max_pattern = r'(?:less than|under|below|at most|maximum|<\s*)(\d+)\s*(?:hp|hit points)'
    hp_max_match = re.search(hp_max_pattern, message_lower)
    
    hp_exact_pattern = r'(\d+)\s*(?:hp|hit points)'
    hp_exact_match = re.search(hp_exact_pattern, message_lower)
    
    # If we have type + HP filter, this is an advanced TCG query
    if (type_match or has_advanced_keyword) and (hp_match or hp_max_match or hp_exact_match):
        search_params = {
            'is_advanced': True,
            'types': [],
            'hp_min': None,
            'hp_max': None
        }
        
        if type_match:
            type_name = type_match.group(1).capitalize()
            # Map some type names
            type_mapping = {'dark': 'Darkness', 'steel': 'Metal', 'normal': 'Colorless'}
            search_params['types'] = [type_mapping.get(type_name.lower(), type_name)]
        
        if hp_match:
            search_params['hp_min'] = int(hp_match.group(1))
        if hp_max_match:
            search_params['hp_max'] = int(hp_max_match.group(1))
        
        return True, search_params
    
    # Standard TCG keyword detection
    if has_tcg_keyword:
        # TCG-specific patterns - order matters, more specific first
        tcg_patterns = [
            # "show me pikachu cards" or "find charizard cards"
            r"(?:show|find|search|get|display)\s+(?:me\s+)?(\w+)\s+(?:card|cards)",
            # "pikachu cards" or "charizard card"
            r"\b(\w+)\s+(?:card|cards)\b",
            # "cards for pikachu" or "cards of charizard"
            r"(?:card|cards)\s+(?:for|of)\s+(\w+)",
            # "show me cards for pikachu"
            r"(?:show|find|search|get|display).*(?:card|cards).*(?:for|of)\s+(\w+)",
        ]
        
        for pattern in tcg_patterns:
            match = re.search(pattern, message_lower)
            if match:
                pokemon_name = match.group(1)
                # Filter out common words and TCG keywords
                skip_words = ['the', 'a', 'an', 'for', 'of', 'me', 'some', 'all', 'any', 
                              'show', 'find', 'search', 'get', 'display', 'pokemon', 'trading']
                if pokemon_name not in skip_words and len(pokemon_name) > 1:
                    return True, pokemon_name
        
        # If TCG keyword present but no specific pokemon found, look for pokemon names
        words = message_lower.split()
        skip_words = tcg_keywords + ['show', 'find', 'search', 'get', 'display', 'the', 'for', 'some', 'all', 'any', 'me', 'pokemon', 'trading']
        for word in words:
            if word not in skip_words and len(word) > 2 and word.isalpha():
                return True, word
    
    return False, None


def generate_response(message: str, user_id: str = "default", card_context: Optional[str] = None) -> dict:
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
            from tool_handlers import execute_tool
            
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
            print(f"Azure OpenAI error: {e}")
            # Fall back to rule-based response
            response_data["message"] = f"I'm having trouble connecting to my AI brain. Error: {str(e)}"
    else:
        # Fallback to rule-based detection (original logic)
        response_data = generate_rule_based_response(message, user_id)
    
    # Add response to history
    conversations[user_id].append({
        "role": "assistant",
        "content": response_data["message"],
        "pokemon_data": response_data.get("pokemon_data"),
        "tcg_data": response_data.get("tcg_data"),
        "timestamp": response_data["timestamp"]
    })
    
    return response_data


def generate_rule_based_response(message: str, user_id: str = "default") -> dict:
    """
    Fallback rule-based response generation (original logic)
    Used when Azure OpenAI is not configured
    """
    response_data = {
        "message": "",
        "pokemon_data": None,
        "tcg_data": None,
        "timestamp": time.time()
    }
    
    # Check for TCG query first (more specific)
    is_tcg_query, tcg_search_param = detect_tcg_query(message)
    
    # Check for Pokemon data query
    is_pokemon_query, pokemon_name = detect_pokemon_query(message)
    
    # Determine which TCG tool to use (MCP preferred if enabled)
    use_mcp_tcg = tool_manager.is_tool_enabled("pokemon_tcg_mcp")
    use_direct_tcg = tool_manager.is_tool_enabled("pokemon_tcg")
    
    # Handle TCG queries if either TCG tool is enabled
    if is_tcg_query and tcg_search_param and (use_mcp_tcg or use_direct_tcg):
        cards_data = None
        search_query = ""
        
        try:
            # Check if it's an advanced search (dict) or simple name search (string)
            if isinstance(tcg_search_param, dict) and tcg_search_param.get('is_advanced'):
                # Advanced search with filters
                search_desc = []
                if tcg_search_param.get('types'):
                    search_desc.append(f"{', '.join(tcg_search_param['types'])}-type")
                if tcg_search_param.get('hp_min'):
                    search_desc.append(f"HP > {tcg_search_param['hp_min']}")
                if tcg_search_param.get('hp_max'):
                    search_desc.append(f"HP < {tcg_search_param['hp_max']}")
                search_query = " ".join(search_desc) if search_desc else "filtered cards"
                
                if use_mcp_tcg:
                    # Use MCP server
                    try:
                        hp_filter = None
                        if tcg_search_param.get('hp_min'):
                            hp_filter = f"[{tcg_search_param['hp_min']} TO *]"
                        elif tcg_search_param.get('hp_max'):
                            hp_filter = f"[* TO {tcg_search_param['hp_max']}]"
                        
                        # MCP expects types as a string, not a list
                        types_str = tcg_search_param.get('types', [None])[0] if tcg_search_param.get('types') else None
                        
                        result = mcp_search_cards(
                            types=types_str,
                            hp=hp_filter,
                            page_size=6
                        )
                        mcp_result = format_cards_for_display(result)
                        if "cards" in mcp_result:
                            formatted_cards = mcp_result["cards"]
                            cards_data = {"data": formatted_cards, "totalCount": mcp_result.get("count", len(formatted_cards))}
                    except Exception as e:
                        print(f"MCP error, falling back to direct API: {e}")
                        use_mcp_tcg = False
                        use_direct_tcg = True
                
                if not cards_data and use_direct_tcg:
                    # Use direct API (or fallback)
                    cards_data = pokemon_tcg_tools.search_cards_advanced(
                        types=tcg_search_param.get('types'),
                        hp_min=tcg_search_param.get('hp_min'),
                        hp_max=tcg_search_param.get('hp_max'),
                        page_size=6
                    )
            else:
                # Simple name search
                search_query = tcg_search_param
                
                if use_mcp_tcg:
                    # Use MCP server
                    try:
                        result = mcp_search_cards(name=tcg_search_param, page_size=6)
                        mcp_result = format_cards_for_display(result)
                        if "cards" in mcp_result:
                            formatted_cards = mcp_result["cards"]
                            cards_data = {"data": formatted_cards, "totalCount": mcp_result.get("count", len(formatted_cards))}
                    except Exception as e:
                        print(f"MCP error, falling back to direct API: {e}")
                        use_mcp_tcg = False
                        use_direct_tcg = True
                
                if not cards_data and use_direct_tcg:
                    # Use direct API (or fallback)
                    cards_data = pokemon_tcg_tools.search_cards(tcg_search_param, page_size=6)
        except Exception as e:
            print(f"TCG query error: {e}")
            response_data["message"] = f"Sorry, there was an error searching for cards: {str(e)}"
        
        if cards_data and cards_data.get("data"):
            if use_mcp_tcg:
                formatted_cards = cards_data["data"]  # Already formatted by MCP
            else:
                formatted_cards = pokemon_tcg_tools.format_cards_response(cards_data)
            response_data["tcg_data"] = {
                "cards": formatted_cards,
                "total_count": cards_data.get("totalCount", 0),
                "search_query": search_query
            }
            # Build response message
            total = cards_data.get("totalCount", 0)
            response_data["message"] = f"**Trading Card Search Results** ({total} cards found)\n\n"
            for card in formatted_cards[:5]:
                response_data["message"] += f"**{card['name']}**"
                # Handle set as string (MCP) or dict (direct API)
                set_info = card.get('set')
                if isinstance(set_info, dict):
                    set_name = set_info.get('name')
                else:
                    set_name = set_info
                if set_name:
                    response_data["message"] += f" - {set_name}"
                response_data["message"] += "\n"
                if card.get('types'):
                    response_data["message"] += f"Type: {', '.join(card['types'])} | "
                if card.get('hp'):
                    response_data["message"] += f"HP: {card['hp']}"
                response_data["message"] += "\n\n"
        else:
            response_data["message"] = f"Sorry, I couldn't find any trading cards matching '{search_query}'."
    
    # Handle Pokemon data queries if the tool is enabled
    elif is_pokemon_query and pokemon_name and tool_manager.is_tool_enabled("pokeapi"):
        pokemon_info = pokemon_tools.get_pokemon(pokemon_name)
        if pokemon_info:
            species_info = pokemon_tools.get_pokemon_species(pokemon_name)
            formatted_info = pokemon_tools.format_pokemon_info(pokemon_info, species_info)
            
            response_data["pokemon_data"] = formatted_info
            response_data["message"] = pokemon_tools.search_pokemon(pokemon_name)
        else:
            response_data["message"] = f"Sorry, I couldn't find information about '{pokemon_name}'. Please check the spelling or try a different Pokemon!"
    
    # General conversation response
    elif not response_data["message"]:
        if any(word in message.lower() for word in ['hello', 'hi', 'hey']):
            response_data["message"] = "Hello! I'm your Pokemon assistant. Ask me about any Pokemon and I'll provide you with detailed information, images, and stats!"
        elif any(word in message.lower() for word in ['help', 'what can you do']):
            enabled_tools = tool_manager.get_enabled_tools()
            tool_list = ", ".join([f"{t.icon} {t.name}" for t in enabled_tools])
            response_data["message"] = f"I can help you learn about Pokemon! Currently enabled tools: {tool_list}\n\nTry:\n- 'Tell me about Pikachu' (Pokemon data)\n- 'Show me Pikachu cards' (Trading cards)\n- Or just type a Pokemon name!"
        elif 'list' in message.lower() or 'random' in message.lower():
            if tool_manager.is_tool_enabled("pokeapi"):
                pokemon_list = pokemon_tools.get_pokemon_list(limit=10)
                names = [p['name'].title() for p in pokemon_list]
                response_data["message"] = f"Here are some Pokemon you can ask about: {', '.join(names)}"
            else:
                response_data["message"] = "Pokemon list is not available. Please enable the PokeAPI tool in settings."
        else:
            response_data["message"] = "I'm a Pokemon expert! Ask me about any Pokemon and I'll show you their stats, abilities, and images. Try asking 'Tell me about Pikachu' or 'Show me Pikachu cards'!"
    
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


@app.route('/api/pokemon/<name_or_id>', methods=['GET'])
def get_pokemon(name_or_id):
    """
    Get Pokemon information by name or ID
    
    Args:
        name_or_id: Pokemon name or ID
        
    Returns:
        JSON with Pokemon data
    """
    try:
        pokemon_info = pokemon_tools.get_pokemon(name_or_id)
        if not pokemon_info:
            return jsonify({"error": f"Pokemon '{name_or_id}' not found"}), 404
        
        species_info = pokemon_tools.get_pokemon_species(name_or_id)
        formatted_info = pokemon_tools.format_pokemon_info(pokemon_info, species_info)
        
        return jsonify(formatted_info)
    
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
    from tool_handlers import execute_tool
    
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


# ============= TCG API Endpoints =============

@app.route('/api/tcg/cards', methods=['GET'])
def search_tcg_cards():
    """
    Search for Pokemon TCG cards
    
    Query params:
        q: Search query (card/pokemon name)
        page: Page number (default 1)
        pageSize: Results per page (default 10)
        
    Returns:
        JSON with card search results
    """
    try:
        query = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('pageSize', 10))
        
        if not query:
            return jsonify({"error": "Query parameter 'q' is required"}), 400
        
        cards_data = pokemon_tcg_tools.search_cards(query, page=page, page_size=page_size)
        
        if not cards_data:
            return jsonify({"error": "Failed to fetch cards"}), 500
        
        formatted_cards = pokemon_tcg_tools.format_cards_response(cards_data)
        
        return jsonify({
            "cards": formatted_cards,
            "total_count": cards_data.get("totalCount", 0),
            "page": cards_data.get("page", 1),
            "page_size": cards_data.get("pageSize", 10)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tcg/cards/<card_id>', methods=['GET'])
def get_tcg_card(card_id):
    """
    Get a specific TCG card by ID
    
    Args:
        card_id: The card ID
        
    Returns:
        JSON with card data
    """
    try:
        card_data = pokemon_tcg_tools.get_card(card_id)
        
        if not card_data or not card_data.get("data"):
            return jsonify({"error": f"Card '{card_id}' not found"}), 404
        
        formatted_card = pokemon_tcg_tools.format_card_info(card_data.get("data"))
        return jsonify(formatted_card)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tcg/sets', methods=['GET'])
def get_tcg_sets():
    """
    Get list of TCG sets
    
    Query params:
        page: Page number (default 1)
        pageSize: Results per page (default 20)
        
    Returns:
        JSON with set data
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('pageSize', 20))
        
        sets_data = pokemon_tcg_tools.get_sets(page=page, page_size=page_size)
        
        if not sets_data:
            return jsonify({"error": "Failed to fetch sets"}), 500
        
        return jsonify(sets_data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Create templates and static directories if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
