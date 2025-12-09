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

# MCP Server configuration for native integration (optional)
# Set these if you want to use native MCP server support instead of function-based tools
POKE_MCP_SERVER_URL = os.getenv('POKE_MCP_SERVER_URL', '')  # e.g., http://localhost:3001
PTCG_MCP_SERVER_URL = os.getenv('PTCG_MCP_SERVER_URL', '')  # e.g., http://localhost:3002

# Feature flags
USE_NATIVE_MCP = os.getenv('USE_NATIVE_MCP', 'false').lower() == 'true'

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

def get_session_config(use_native_mcp=None):
    """
    Get the session configuration to send after WebSocket connection.
    This configures the Realtime API session for Pokemon assistant.
    
    Args:
        use_native_mcp: Override for USE_NATIVE_MCP setting. If None, uses env var.
    """
    if use_native_mcp is None:
        use_native_mcp = USE_NATIVE_MCP
    
    session_config = {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": """You are PokéChat, a friendly and knowledgeable Pokemon assistant. 
You help users learn about Pokemon, their abilities, types, evolutions, and more.
Keep responses conversational and concise since this is a voice conversation.
Be enthusiastic about Pokemon but don't be too verbose - aim for natural speech patterns.
If asked about specific Pokemon, provide key details like type, abilities, and interesting facts.
You can also discuss Pokemon cards, games, and general Pokemon knowledge. The only languages used by the users are English, Danish, Cantonese. Do not respond in any other language.
You can also analyze images that users share with you - just describe what you see if they ask. Respond with short sentences.""",
            "voice": "alloy",  # Options: alloy, echo, shimmer
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
    
    # Add tools based on configuration
    if use_native_mcp:
        # Use native MCP server integration (requires HTTP-accessible MCP servers)
        session_config["session"]["tools"] = get_native_mcp_tools()
    else:
        # Use function-based tools (handled by client-side /api/realtime/tool endpoint)
        session_config["session"]["tools"] = get_available_tools()
    
    return session_config


def get_native_mcp_tools():
    """
    Get MCP server configurations for native Realtime API MCP support.
    This allows the API to directly call MCP servers without client-side handling.
    
    Note: MCP servers must be running as HTTP/SSE services with accessible URLs.
    The server_url should point to the SSE endpoint (e.g., http://localhost:3001/sse)
    """
    tools = []
    
    if POKE_MCP_SERVER_URL:
        # Ensure the URL points to the SSE endpoint
        url = POKE_MCP_SERVER_URL.rstrip('/')
        if not url.endswith('/sse'):
            url = f"{url}/sse"
        tools.append({
            "type": "mcp",
            "server_label": "pokedex",
            "server_url": url,
            "require_approval": "never"
        })
    
    if PTCG_MCP_SERVER_URL:
        # Ensure the URL points to the SSE endpoint
        url = PTCG_MCP_SERVER_URL.rstrip('/')
        if not url.endswith('/sse'):
            url = f"{url}/sse"
        tools.append({
            "type": "mcp",
            "server_label": "pokemon_tcg",
            "server_url": url,
            "require_approval": "never"
        })
    
    # If no MCP servers configured, fall back to function tools
    if not tools:
        return get_available_tools()
    
    return tools

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
