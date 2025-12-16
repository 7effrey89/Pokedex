import requests
import json
import os

url = 'http://127.0.0.1:5000/api/pokemon/pikachu'

print("Testing local Pokemon API endpoint...")
print(f"URL: {url}")
print("-" * 60)

resp = requests.get(url, timeout=30)
resp.raise_for_status()
data = resp.json()

# Print summary
print(f"✅ Success!")
print(f"Pokemon: {data.get('name', 'Unknown').title()}")
print(f"ID: {data.get('id')}")
if data.get('types'):
    print(f"Types: {', '.join(data.get('types', []))}")

# Attempt to print chosen cover image candidates
print('\n-- Candidate images --')
sprites = data.get('sprites') or {}
if data.get('image'):
    print('image:', data.get('image'))
if data.get('sprite'):
    print('sprite:', data.get('sprite'))

# Save full response to file
output_file = os.path.join(os.path.dirname(__file__), "call_get_pokemon_response.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nFull response saved to: {output_file}")
