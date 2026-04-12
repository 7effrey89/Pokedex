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


def _sanitize_endpoint(value: str) -> str:
    endpoint = (value or '').strip().rstrip('/')

    project_marker = '/api/projects/'
    project_idx = endpoint.find(project_marker)
    if project_idx != -1:
        endpoint = endpoint[:project_idx]

    if endpoint.endswith('/openai'):
        endpoint = endpoint[:-len('/openai')]
    elif '/openai/' in endpoint:
        endpoint = endpoint.split('/openai/', 1)[0]

    return endpoint.rstrip('/')


def _is_service_principal_mode() -> bool:
    return os.getenv("AZURE_AUTH_MODE", "key").strip().lower() == "service_principal"


_DEFAULT_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


def _get_sp_access_token() -> str:
    """Get a fresh access token using service-principal credentials."""
    from azure.identity import ClientSecretCredential
    credential = ClientSecretCredential(
        tenant_id=os.getenv("AZURE_TENANT_ID", ""),
        client_id=os.getenv("AZURE_CLIENT_ID", ""),
        client_secret=os.getenv("AZURE_CLIENT_SECRET", ""),
    )
    scope = os.getenv("AZURE_TOKEN_SCOPE", _DEFAULT_TOKEN_SCOPE)
    token = credential.get_token(scope)
    return token.token


DEFAULT_REALTIME_CONFIG = {
    'endpoint': _sanitize_endpoint(
        os.getenv('AZURE_OPENAI_REALTIME_ENDPOINT')
        or os.getenv('AZURE_OPENAI_ENDPOINT')
        or os.getenv('FOUNDRY_PROJECT_ENDPOINT', '')
    ),
    'api_key': os.getenv('AZURE_OPENAI_REALTIME_KEY', os.getenv('AZURE_OPENAI_API_KEY', '')),
    'deployment': os.getenv('AZURE_OPENAI_REALTIME_DEPLOYMENT', 'gpt-realtime'),
    'api_version': os.getenv('AZURE_OPENAI_REALTIME_API_VERSION', '2024-10-01-preview')
}


def _build_realtime_ws_url(endpoint: str, deployment: str, api_version: str) -> str:
    endpoint_host = endpoint.replace('https://', '').replace('http://', '')
    normalized_api_version = (api_version or '').strip().lower()

    if normalized_api_version.endswith('preview'):
        return f"wss://{endpoint_host}/openai/realtime?api-version={api_version}&deployment={deployment}"

    return f"wss://{endpoint_host}/openai/v1/realtime?model={deployment}"

def get_realtime_config(overrides=None):
    """
    Get the configuration for Azure OpenAI Realtime API connection.
    Returns WebSocket URL and headers/token for the browser to connect directly.
    """
    cfg = (overrides or DEFAULT_REALTIME_CONFIG).copy()
    endpoint = _sanitize_endpoint(cfg.get('endpoint', ''))
    deployment = cfg.get('deployment', DEFAULT_REALTIME_CONFIG['deployment'])
    api_version = cfg.get('api_version', DEFAULT_REALTIME_CONFIG['api_version'])
    auth_mode = str(cfg.get('auth_mode') or ('service_principal' if _is_service_principal_mode() and not overrides else 'api_key')).strip().lower()
    use_sp = auth_mode == 'service_principal'

    if use_sp:
        if not endpoint or not deployment:
            raise ValueError("Azure OpenAI credentials not configured")
        access_token = _get_sp_access_token()
        ws_url = _build_realtime_ws_url(endpoint, deployment, api_version)
        return {
            'ws_url': ws_url,
            'access_token': access_token,
            'auth_mode': 'service_principal',
            'deployment': deployment,
            'api_version': api_version
        }

    api_key = cfg.get('api_key', '')
    if not endpoint or not api_key or not deployment:
        raise ValueError("Azure OpenAI credentials not configured")

    ws_url = _build_realtime_ws_url(endpoint, deployment, api_version)
    
    return {
        'ws_url': ws_url,
        'api_key': api_key,
        'auth_mode': 'api_key',
        'deployment': deployment,
        'api_version': api_version
    }

def get_session_config(preferred_language=None):
    """
    Get the session configuration to send after WebSocket connection.
    This configures the Realtime API session for Pokemon assistant.
    """
    from src.tools.tool_definitions import get_system_prompt_realtime
    normalized_language = (preferred_language or 'english').strip().lower()

    session_config = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": get_system_prompt_realtime(normalized_language),
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": 24000
                    },
                    "transcription": {
                        "model": "whisper-1"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                        "create_response": True,
                        "interrupt_response": True
                    }
                },
                "output": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": 24000
                    },
                    "voice": "alloy"
                }
            },
        }
    }

    # Use function-based tools
    session_config["session"]["tools"] = get_available_tools()
    
    return session_config


def get_available_tools():
    """
    Get the tools configuration for the Realtime API session.
    Uses the shared tool registry (single source of truth).
    """
    from src.tools.tool_definitions import get_tools_realtime_format
    return get_tools_realtime_format()


def check_realtime_availability(overrides=None):
    """
    Check if Azure OpenAI Realtime API is available and configured.
    """
    cfg = (overrides or DEFAULT_REALTIME_CONFIG).copy()
    endpoint = _sanitize_endpoint(cfg.get('endpoint', ''))
    deployment = cfg.get('deployment', DEFAULT_REALTIME_CONFIG['deployment'])
    api_version = cfg.get('api_version', DEFAULT_REALTIME_CONFIG['api_version'])
    auth_mode = str(cfg.get('auth_mode') or ('service_principal' if _is_service_principal_mode() and not overrides else 'api_key')).strip().lower()

    if not endpoint:
        return {'available': False, 'message': 'Azure OpenAI endpoint not configured', 'details': {}}

    use_sp = auth_mode == 'service_principal'
    if not use_sp:
        api_key = cfg.get('api_key', '')
        if not api_key:
            return {'available': False, 'message': 'Azure OpenAI API key not configured', 'details': {}}

    if not deployment:
        return {'available': False, 'message': 'Realtime deployment not configured', 'details': {}}

    return {
        'available': True,
        'message': 'Realtime API configured',
        'details': {
            'deployment': deployment,
            'api_version': api_version,
            'auth_mode': 'service_principal' if use_sp else 'api_key'
        }
    }
