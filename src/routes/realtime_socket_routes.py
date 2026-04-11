"""Server-side WebSocket relay for Azure OpenAI Realtime sessions."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from typing import Any, Dict, Optional

from flask import current_app
from flask_sock import Sock
from websockets.sync.client import connect as ws_connect

from realtime_chat import get_realtime_config, get_session_config


logger = logging.getLogger(__name__)

sock = Sock()

_RELAY_SESSION_TTL_SECONDS = 300
_relay_sessions: Dict[str, Dict[str, Any]] = {}
_relay_lock = threading.Lock()


def init_realtime_socket_routes(app) -> None:
    sock.init_app(app)


def _cleanup_expired_sessions() -> None:
    now = time.time()
    expired = []
    with _relay_lock:
        for session_id, payload in _relay_sessions.items():
            created_at = float(payload.get('created_at', 0))
            if now - created_at > _RELAY_SESSION_TTL_SECONDS:
                expired.append(session_id)
        for session_id in expired:
            _relay_sessions.pop(session_id, None)


def create_relay_session(realtime_config: Dict[str, str], preferred_language: Optional[str], preferred_voice: Optional[str]) -> str:
    _cleanup_expired_sessions()
    session_id = uuid.uuid4().hex
    session_config = get_session_config(preferred_language)
    if preferred_voice:
        session_config.setdefault('session', {}).setdefault('audio', {}).setdefault('output', {})['voice'] = preferred_voice

    with _relay_lock:
        _relay_sessions[session_id] = {
            'created_at': time.time(),
            'realtime_config': dict(realtime_config),
            'session_config': session_config,
        }
    return session_id


def _get_relay_session(session_id: str) -> Optional[Dict[str, Any]]:
    _cleanup_expired_sessions()
    with _relay_lock:
        payload = _relay_sessions.get(session_id)
        return dict(payload) if payload else None


def _build_azure_headers(config: Dict[str, str]) -> Dict[str, str]:
    resolved = get_realtime_config(config)
    if resolved.get('auth_mode') == 'service_principal':
        return {
            'Authorization': f"Bearer {resolved['access_token']}"
        }
    return {
        'api-key': resolved['api_key']
    }


def _send_local_error(ws, message: str) -> None:
    try:
        ws.send(json.dumps({
            'type': 'error',
            'error': {
                'message': message,
            }
        }))
    except Exception:
        logger.debug('Unable to send local realtime relay error to browser', exc_info=True)


@sock.route('/api/realtime/ws/<session_id>')
def realtime_ws_relay(ws, session_id: str) -> None:
    relay_session = _get_relay_session(session_id)
    if not relay_session:
        _send_local_error(ws, 'Realtime relay session expired. Refresh the page and try voice again.')
        return

    realtime_config = relay_session['realtime_config']
    session_config = relay_session['session_config']
    resolved_config = get_realtime_config(realtime_config)
    azure_headers = _build_azure_headers(realtime_config)
    stop_event = threading.Event()

    try:
        with ws_connect(
            resolved_config['ws_url'],
            additional_headers=azure_headers,
            open_timeout=20,
            close_timeout=5,
            max_size=None,
        ) as azure_ws:
            azure_ws.send(json.dumps(session_config))

            def azure_to_browser() -> None:
                try:
                    for message in azure_ws:
                        if stop_event.is_set():
                            break
                        ws.send(message)
                except Exception as exc:
                    if not stop_event.is_set():
                        logger.warning('Azure realtime relay receive loop ended: %s', exc)
                        _send_local_error(ws, f'Realtime relay receive error: {exc}')
                finally:
                    stop_event.set()

            receiver_thread = threading.Thread(target=azure_to_browser, daemon=True)
            receiver_thread.start()

            try:
                while not stop_event.is_set():
                    browser_message = ws.receive()
                    if browser_message is None:
                        break
                    azure_ws.send(browser_message)
            finally:
                stop_event.set()
                try:
                    azure_ws.close()
                except Exception:
                    logger.debug('Azure realtime relay close failed', exc_info=True)
                receiver_thread.join(timeout=1)
    except Exception as exc:
        logger.exception('Realtime relay setup failed')
        _send_local_error(ws, f'Realtime relay connection failed: {exc}')