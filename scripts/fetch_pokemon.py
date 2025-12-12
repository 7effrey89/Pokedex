import requests
import json

API = "https://pokeapi.co/api/v2/pokemon/pikachu"

resp = requests.get(API, timeout=30)
resp.raise_for_status()

data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False))
