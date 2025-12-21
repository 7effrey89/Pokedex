"""Utility helpers for resolving API credential payloads from the client."""
import os
from typing import Any, Dict, Optional

APP_API_PASSWORD = os.getenv('APP_API_PASSWORD', 'Password1')


def _sanitize_endpoint(value: str) -> str:
    if not value:
        return ''
    return value.strip().rstrip('/')


def _require_fields(values: Dict[str, str], name: str) -> None:
    missing = [field for field, val in values.items() if not val]
    if missing:
        raise ValueError(f"Missing {name} field(s): {', '.join(missing)}")


def _resolve_env_chat_config() -> Dict[str, str]:
    chat_endpoint = _sanitize_endpoint(os.getenv('AZURE_OPENAI_ENDPOINT', ''))
    chat_key = os.getenv('AZURE_OPENAI_API_KEY', '').strip()
    chat_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', '').strip()
    chat_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-10-21').strip()
    _require_fields(
        {
            'AZURE_OPENAI_ENDPOINT': chat_endpoint,
            'AZURE_OPENAI_API_KEY': chat_key,
            'AZURE_OPENAI_DEPLOYMENT': chat_deployment
        },
        'environment'
    )
    return {
        'endpoint': chat_endpoint,
        'api_key': chat_key,
        'deployment': chat_deployment,
        'api_version': chat_api_version or '2024-10-21'
    }


def _resolve_env_realtime_config() -> Dict[str, str]:
    realtime_endpoint = _sanitize_endpoint(
        os.getenv('AZURE_OPENAI_REALTIME_ENDPOINT', os.getenv('AZURE_OPENAI_ENDPOINT', ''))
    )
    realtime_key = os.getenv('AZURE_OPENAI_REALTIME_KEY', os.getenv('AZURE_OPENAI_API_KEY', '')).strip()
    deployment = os.getenv('AZURE_OPENAI_REALTIME_DEPLOYMENT', '').strip()
    api_version = os.getenv('AZURE_OPENAI_REALTIME_API_VERSION', '2024-10-01-preview').strip()
    _require_fields(
        {
            'AZURE_OPENAI_ENDPOINT': realtime_endpoint,
            'AZURE_OPENAI_API_KEY': realtime_key,
            'AZURE_OPENAI_REALTIME_DEPLOYMENT': deployment
        },
        'environment'
    )
    return {
        'endpoint': realtime_endpoint,
        'api_key': realtime_key,
        'deployment': deployment,
        'api_version': api_version or '2024-10-01-preview'
    }


def _resolve_custom_chat_config(custom: Dict[str, Any]) -> Dict[str, str]:
    chat_endpoint = _sanitize_endpoint(str(custom.get('chat_endpoint', '')).strip())
    chat_key = str(custom.get('chat_api_key', '')).strip()
    chat_deployment = str(custom.get('chat_deployment', '')).strip()
    _require_fields(
        {
            'chat_endpoint': chat_endpoint,
            'chat_api_key': chat_key,
            'chat_deployment': chat_deployment
        },
        'custom chat'
    )
    return {
        'endpoint': chat_endpoint,
        'api_key': chat_key,
        'deployment': chat_deployment,
        'api_version': str(custom.get('chat_api_version', '2024-10-21')).strip() or '2024-10-21'
    }


def _resolve_custom_realtime_config(custom: Dict[str, Any], chat_config: Dict[str, str]) -> Dict[str, str]:
    realtime_endpoint = _sanitize_endpoint(str(custom.get('realtime_endpoint', chat_config['endpoint'])).strip())
    realtime_key = str(custom.get('realtime_api_key', chat_config['api_key'])).strip()
    realtime_deployment = str(custom.get('realtime_deployment', chat_config['deployment'])).strip()
    realtime_api_version = str(custom.get('realtime_api_version', '2024-10-01-preview')).strip() or '2024-10-01-preview'
    _require_fields(
        {
            'realtime_endpoint': realtime_endpoint,
            'realtime_api_key': realtime_key,
            'realtime_deployment': realtime_deployment
        },
        'custom realtime'
    )
    return {
        'endpoint': realtime_endpoint,
        'api_key': realtime_key,
        'deployment': realtime_deployment,
        'api_version': realtime_api_version
    }


def _resolve_tcg_config(override_key: Optional[str] = None, *, allow_env_fallback: bool = True) -> Optional[Dict[str, str]]:
    key = str(override_key or '').strip()
    if key:
        return {'api_key': key}
    if allow_env_fallback:
        env_key = str(os.getenv('POKEMON_TCG_API_KEY', '')).strip()
        if env_key:
            return {'api_key': env_key}
    return None


def resolve_api_settings(payload: Optional[Dict[str, Any]], *, require_chat: bool = True, require_realtime: bool = False) -> Dict[str, Dict[str, str]]:
    """Resolve API credentials from incoming payload or environment defaults."""
    if not payload:
        raise ValueError('API settings are required.')

    mode = str(payload.get('mode', '')).lower()
    settings: Dict[str, Dict[str, str]] = {}

    if mode == 'app':
        password = payload.get('app_password', '')
        if password != APP_API_PASSWORD:
            raise ValueError('Invalid API access password.')
        if require_chat:
            settings['chat'] = _resolve_env_chat_config()
        else:
            try:
                settings['chat'] = _resolve_env_chat_config()
            except ValueError:
                pass
        if require_realtime:
            settings['realtime'] = _resolve_env_realtime_config()
        else:
            try:
                settings['realtime'] = _resolve_env_realtime_config()
            except ValueError:
                pass
        tcg_config = _resolve_tcg_config(payload.get('tcg_api_key'))
        if tcg_config:
            settings['tcg'] = tcg_config
        return settings

    if mode == 'custom':
        custom_payload = payload.get('custom') or {}
        chat_config = _resolve_custom_chat_config(custom_payload) if require_chat else None
        if chat_config:
            settings['chat'] = chat_config
        elif not require_chat:
            try:
                settings['chat'] = _resolve_custom_chat_config(custom_payload)
            except ValueError:
                pass
        realtime_config = _resolve_custom_realtime_config(custom_payload, chat_config or settings.get('chat', {}))
        if realtime_config:
            settings['realtime'] = realtime_config
        tcg_config = _resolve_tcg_config(custom_payload.get('tcg_api_key'))
        if tcg_config:
            settings['tcg'] = tcg_config
        return settings

    raise ValueError('Unknown API settings mode. Choose "app" or "custom".')
