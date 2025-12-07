"""
Flask backend for Pokemon Chat Demo
Provides API endpoints for real-time chat with Pokemon lookup capabilities
"""
import os
import json
from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from dotenv import load_dotenv
from pokemon_tools import PokemonTools
import time
import re

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Initialize Pokemon tools
pokemon_tools = PokemonTools()

# Store conversation history (in production, use a database)
conversations = {}


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


def generate_response(message: str, user_id: str = "default") -> dict:
    """
    Generate a response to the user message
    
    Args:
        message: User message
        user_id: User identifier
        
    Returns:
        Dict containing response data
    """
    # Initialize conversation history if needed
    if user_id not in conversations:
        conversations[user_id] = []
    
    # Add user message to history
    conversations[user_id].append({
        "role": "user",
        "content": message,
        "timestamp": time.time()
    })
    
    # Check if this is a Pokemon query
    is_pokemon_query, pokemon_name = detect_pokemon_query(message)
    
    response_data = {
        "message": "",
        "pokemon_data": None,
        "timestamp": time.time()
    }
    
    if is_pokemon_query and pokemon_name:
        # Fetch Pokemon information
        pokemon_info = pokemon_tools.get_pokemon(pokemon_name)
        if pokemon_info:
            species_info = pokemon_tools.get_pokemon_species(pokemon_name)
            formatted_info = pokemon_tools.format_pokemon_info(pokemon_info, species_info)
            
            response_data["pokemon_data"] = formatted_info
            response_data["message"] = pokemon_tools.search_pokemon(pokemon_name)
        else:
            response_data["message"] = f"Sorry, I couldn't find information about '{pokemon_name}'. Please check the spelling or try a different Pokemon!"
    else:
        # General conversation response
        if any(word in message.lower() for word in ['hello', 'hi', 'hey']):
            response_data["message"] = "Hello! I'm your Pokemon assistant. Ask me about any Pokemon and I'll provide you with detailed information, images, and stats!"
        elif any(word in message.lower() for word in ['help', 'what can you do']):
            response_data["message"] = "I can help you learn about Pokemon! Just ask me about any Pokemon by name or ID. For example:\n- 'Tell me about Pikachu'\n- 'Show me Charizard'\n- 'What is Mewtwo'\n- Or just type the Pokemon name!"
        elif 'list' in message.lower() or 'random' in message.lower():
            pokemon_list = pokemon_tools.get_pokemon_list(limit=10)
            names = [p['name'].title() for p in pokemon_list]
            response_data["message"] = f"Here are some Pokemon you can ask about: {', '.join(names)}"
        else:
            response_data["message"] = "I'm a Pokemon expert! Ask me about any Pokemon and I'll show you their stats, abilities, and images. Try asking 'Tell me about Pikachu' or just type a Pokemon name!"
    
    # Add response to history
    conversations[user_id].append({
        "role": "assistant",
        "content": response_data["message"],
        "pokemon_data": response_data.get("pokemon_data"),
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
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        response_data = generate_response(message, user_id)
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
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        def generate():
            response_data = generate_response(message, user_id)
            
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


if __name__ == '__main__':
    # Create templates and static directories if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
