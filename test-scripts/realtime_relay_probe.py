import asyncio
import json

import requests
from websockets.client import connect


def get_relay_url() -> str:
    response = requests.post(
        'http://127.0.0.1:5000/api/realtime/config',
        json={
            'api_settings': {
                'mode': 'app',
                'app_password': 'Password1',
            },
            'voice': 'alloy',
            'language': 'english',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    relay_url = payload.get('relay_url')
    if not relay_url:
        raise RuntimeError(f'No relay_url returned: {payload}')
    return relay_url


async def main() -> None:
    relay_path = get_relay_url()
    ws_url = f"ws://127.0.0.1:5000{relay_path}"
    print(f'connecting:{ws_url}')
    async with connect(ws_url, open_timeout=20, close_timeout=5, max_size=None) as ws:
        for _ in range(4):
            message = await asyncio.wait_for(ws.recv(), timeout=15)
            payload = json.loads(message)
            print(payload.get('type'))
            if payload.get('type') in {'session.created', 'session.updated'}:
                return
    raise RuntimeError('Relay did not emit realtime session events.')


if __name__ == '__main__':
    asyncio.run(main())