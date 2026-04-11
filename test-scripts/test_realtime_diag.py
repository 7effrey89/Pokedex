"""Quick diagnostic to test Azure Realtime API session and text response."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from realtime_chat import get_realtime_config, get_session_config, DEFAULT_REALTIME_CONFIG
from websockets.sync.client import connect as ws_connect

overrides = dict(DEFAULT_REALTIME_CONFIG, auth_mode='service_principal')
config = get_realtime_config(overrides)
print('WS URL:', config['ws_url'])
print('Auth mode:', config.get('auth_mode'))
session_config = get_session_config('english')
print('Session config type:', session_config['type'])

headers = {}
if config.get('auth_mode') == 'service_principal':
    headers['Authorization'] = f"Bearer {config['access_token']}"
else:
    headers['api-key'] = config['api_key']

ws = ws_connect(config['ws_url'], additional_headers=headers, open_timeout=20, max_size=None)
print('Connected!')

# Send session config
ws.send(json.dumps(session_config))
print('Sent session config')

# Wait for session.created and session.updated
for i in range(10):
    try:
        msg = json.loads(ws.recv(timeout=5))
        t = msg.get('type', '')
        print(f'Event {i}: {t}')
        if t == 'session.updated':
            sess = msg.get('session', {})
            td = sess.get('turn_detection', sess.get('audio', {}).get('input', {}).get('turn_detection', 'NOT FOUND'))
            print(f'  turn_detection: {json.dumps(td)}')
            audio = sess.get('audio', 'NOT FOUND')
            print(f'  audio: {json.dumps(audio)[:500]}')
            print(f'  full session keys: {list(sess.keys())}')
        elif t == 'error':
            print(f'  ERROR: {json.dumps(msg.get("error", {}))}')
    except Exception as e:
        print(f'Recv timeout/error: {e}')
        break

# Now send a text message and response.create to test if AI responds
ws.send(json.dumps({
    'type': 'conversation.item.create',
    'item': {
        'type': 'message',
        'role': 'user',
        'content': [{'type': 'input_text', 'text': 'Say hello in one word.'}]
    }
}))
ws.send(json.dumps({'type': 'response.create'}))
print('\nSent text + response.create')

for i in range(30):
    try:
        msg = json.loads(ws.recv(timeout=5))
        t = msg.get('type', '')
        if 'audio' in t and 'delta' in t:
            delta = msg.get('delta', '')
            if 'transcript' in t:
                print(f'Event: {t} -> "{delta}"', flush=True)
            else:
                print(f'Event: {t} (audio chunk, {len(delta)} b64 chars)')
        elif t == 'response.done':
            print(f'Event: {t}')
            break
        elif t == 'error':
            print(f'Event: {t}')
            print(f'  ERROR: {json.dumps(msg.get("error", {}))}')
        else:
            print(f'Event: {t}')
    except Exception as e:
        print(f'Recv timeout/error: {e}')
        break

ws.close()
print('\nDone!')
