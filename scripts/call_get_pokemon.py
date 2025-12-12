import requests, json

url = 'http://127.0.0.1:5000/api/pokemon/pikachu'
resp = requests.get(url, timeout=30)
resp.raise_for_status()
data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False))
# Attempt to print chosen cover image candidates
print('\n-- Candidate images --')
sprites = data.get('sprites') or {}
print(json.dumps(sprites, indent=2, ensure_ascii=False))
if data.get('image'):
    print('\nimage:', data.get('image'))
if data.get('sprite'):
    print('sprite:', data.get('sprite'))
