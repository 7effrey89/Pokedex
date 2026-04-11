import asyncio
import json
import os
from dotenv import load_dotenv
from websockets.client import connect
from realtime_chat import get_realtime_config, get_session_config
from src.utils.api_settings import resolve_api_settings

load_dotenv()

async def main():
    settings = resolve_api_settings({'mode':'app','app_password':'Password1'}, require_chat=True, require_realtime=True)
    cfg = get_realtime_config(settings['realtime'])
    ws_url = cfg['ws_url'] + '&access_token=' + cfg['access_token']
    print('connecting', ws_url.split('&access_token=')[0])
    async with connect(ws_url, open_timeout=20, close_timeout=5) as ws:
        print('ws-open')
        await ws.send(json.dumps(get_session_config('english')))
        for _ in range(3):
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            parsed = json.loads(msg)
            print(parsed.get('type'))
            if parsed.get('type') in {'session.created', 'session.updated'}:
                break

asyncio.run(main())
