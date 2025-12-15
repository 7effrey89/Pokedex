import requests
import json
import os

API = "https://pokeapi.co/api/v2/pokemon/pikachu"

print("Fetching Pokemon data from PokeAPI...")
print(f"URL: {API}")
print("-" * 60)

resp = requests.get(API, timeout=30)
resp.raise_for_status()

data = resp.json()

# Print summary
print(f"✅ Success!")
print(f"Pokemon: {data.get('name', 'Unknown').title()}")
print(f"ID: {data.get('id')}")
print(f"Height: {data.get('height')} decimeters")
print(f"Weight: {data.get('weight')} hectograms")
print(f"Types: {', '.join([t['type']['name'] for t in data.get('types', [])])}")
print(f"Abilities: {', '.join([a['ability']['name'] for a in data.get('abilities', [])])}")

# Save full response to file
output_file = os.path.join(os.path.dirname(__file__), "fetch_pokemon_response.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nFull response saved to: {output_file}")
