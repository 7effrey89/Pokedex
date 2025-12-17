"""
Azure OpenAI Realtime API Handler
Provides WebSocket-based real-time voice conversation capabilities
"""
import os
import json
import base64
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Azure OpenAI Realtime API configuration
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '').rstrip('/')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY', '')
AZURE_OPENAI_REALTIME_DEPLOYMENT = os.getenv('AZURE_OPENAI_REALTIME_DEPLOYMENT', 'gpt-realtime')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_REALTIME_API_VERSION', '2024-10-01-preview')

def get_realtime_config():
    """
    Get the configuration for Azure OpenAI Realtime API connection.
    Returns WebSocket URL and headers for the browser to connect directly.
    """
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
        raise ValueError("Azure OpenAI credentials not configured")
    
    # Extract the hostname from the endpoint
    endpoint_host = AZURE_OPENAI_ENDPOINT.replace('https://', '').replace('http://', '')
    
    # Construct the WebSocket URL for Azure OpenAI Realtime API
    # Format: wss://{resource}.openai.azure.com/openai/realtime?api-version={version}&deployment={deployment}
    ws_url = f"wss://{endpoint_host}/openai/realtime?api-version={AZURE_OPENAI_API_VERSION}&deployment={AZURE_OPENAI_REALTIME_DEPLOYMENT}"
    
    return {
        'ws_url': ws_url,
        'api_key': AZURE_OPENAI_API_KEY,
        'deployment': AZURE_OPENAI_REALTIME_DEPLOYMENT,
        'api_version': AZURE_OPENAI_API_VERSION
    }

def get_session_config():
    """
    Get the session configuration to send after WebSocket connection.
    This configures the Realtime API session for Pokemon assistant.
    """
    session_config = {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": """You are Pokédex, a friendly and knowledgeable Pokemon assistant. 
You help users learn about Pokemon, their abilities, types, evolutions, and more.
Keep responses conversational and concise since this is a voice conversation.
Be enthusiastic about Pokemon but don't be too verbose - aim for natural speech patterns.
If asked about specific Pokemon, provide key details like type, abilities, and interesting facts.
You can also discuss Pokemon cards, games, and general Pokemon knowledge. The only languages used by the users are English, Danish, Cantonese. Do not respond in any other language.
Respond with short sentences.

CONTEXT AWARENESS - YOU CAN SEE WHAT THE USER IS VIEWING:
- Your instructions will include a "CURRENT CANVAS CONTENT" section that tells you EXACTLY what the user is viewing in their Pokédex app right now.
- When users ask "what am I looking at?" or "what's on my screen?" or "tell me about this", you SHOULD reference the CURRENT CANVAS CONTENT to describe what they're viewing.
- The canvas content updates automatically as users navigate - you always know whether they're viewing the index page, a specific Pokemon, or a Pokemon card.
- When users send you images via the camera scanner, analyze what you see - this is for identifying physical Pokemon cards.
- Do NOT make up or hallucinate content that isn't in the CURRENT CANVAS CONTENT section.""",
            "voice": "alloy",  # Options: alloy, ash, ballad, cedar, coral, echo, ember, luna, marin, pearl, sage, shimmer, sol, verse
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500
            },
            "temperature": 0.8,
            "max_response_output_tokens": 4096
        }
    }
    
    # Use function-based tools
    session_config["session"]["tools"] = get_available_tools()
    
    return session_config


def get_available_tools():
    """
    Get the tools configuration for the Realtime API session.
    These allow the AI to look up Pokemon information and cards.
    """
    return [
        {
            "type": "function",
            "name": "get_pokemon_info",
            "description": "Get detailed information about a specific Pokemon by name or number. Use this when the user asks about a specific Pokemon.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pokemon_name": {
                        "type": "string",
                        "description": "The name or Pokedex number of the Pokemon to look up (e.g., 'pikachu', 'charizard', '25')"
                    }
                },
                "required": ["pokemon_name"]
            }
        },
        {
            "type": "function", 
            "name": "get_random_pokemon",
            "description": "Get a random Pokemon from the entire Pokedex. Use this when the user wants to discover a random Pokemon or says 'surprise me'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "type": "function",
            "name": "get_random_pokemon_from_region",
            "description": "Get a random Pokemon from a specific region (Kanto, Johto, Hoenn, Sinnoh, Unova, Kalos, Alola, Galar, or Paldea).",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "The Pokemon region name (e.g., 'kanto', 'johto', 'hoenn')",
                        "enum": ["kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "paldea"]
                    }
                },
                "required": ["region"]
            }
        },
        {
            "type": "function",
            "name": "get_random_pokemon_by_type",
            "description": "Get a random Pokemon of a specific type (fire, water, grass, electric, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pokemon_type": {
                        "type": "string",
                        "description": "The Pokemon type (e.g., 'fire', 'water', 'grass', 'electric', 'psychic')"
                    }
                },
                "required": ["pokemon_type"]
            }
        },
        {
            "type": "function",
            "name": "search_pokemon_cards",
            "description": "Search for Pokemon Trading Card Game (TCG) cards. Use this when the user asks about Pokemon cards.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pokemon_name": {
                        "type": "string",
                        "description": "The name of the Pokemon to search for cards (e.g., 'pikachu', 'charizard')"
                    }
                },
                "required": ["pokemon_name"]
            }
        },
        {
            "type": "function",
            "name": "show_tcg_card_by_index",
            "description": "Show a specific TCG card by its number in the current gallery. Only works when TCG cards are already displayed. Use this when user says 'show card 5' or 'open the first card'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_index": {
                        "type": "integer",
                        "description": "The card number to show (1-based index, e.g., 1 for first card, 2 for second card)"
                    },
                    "pokemon_name": {
                        "type": "string",
                        "description": "The name of the Pokemon whose cards are being viewed (optional, for context)"
                    }
                },
                "required": ["card_index"]
            }
        }
    ]

def check_realtime_availability():
    """
    Check if Azure OpenAI Realtime API is available and configured.
    """
    result = {
        'available': False,
        'message': '',
        'details': {}
    }
    
    if not AZURE_OPENAI_ENDPOINT:
        result['message'] = 'Azure OpenAI endpoint not configured'
        return result
    
    if not AZURE_OPENAI_API_KEY:
        result['message'] = 'Azure OpenAI API key not configured'
        return result
    
    if not AZURE_OPENAI_REALTIME_DEPLOYMENT:
        result['message'] = 'Realtime deployment not configured. Add AZURE_OPENAI_REALTIME_DEPLOYMENT to .env'
        return result
    
    result['available'] = True
    result['message'] = 'Realtime API configured'
    result['details'] = {
        'deployment': AZURE_OPENAI_REALTIME_DEPLOYMENT,
        'api_version': AZURE_OPENAI_API_VERSION
    }
    
    return result
